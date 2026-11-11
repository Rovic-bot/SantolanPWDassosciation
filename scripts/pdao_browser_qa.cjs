const fs = require('node:fs');
const path = require('node:path');
const {spawn} = require('node:child_process');
const config = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'));
const directory = path.dirname(process.argv[2]);
const pause = ms => new Promise(resolve => setTimeout(resolve, ms));

(async () => {
  const profile = fs.mkdtempSync(path.join(directory, 'chrome-'));
  const child = spawn(process.env.CHROME_EXECUTABLE || 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe', [
    '--headless=new', '--disable-gpu', '--no-first-run', '--no-default-browser-check',
    '--remote-debugging-port=0', '--user-data-dir=' + profile, 'about:blank'
  ], {windowsHide: true, stdio: ['ignore', 'ignore', 'pipe']});
  let log = '', launchError, socket, send;
  child.on('error', error => { launchError = error; });
  child.stderr.on('data', data => { log += data; });
  try {
    const portFile = path.join(profile, 'DevToolsActivePort');
    for (let i = 0; i < 100 && !fs.existsSync(portFile); i++) {
      if (launchError) throw launchError;
      if (child.exitCode !== null) throw new Error('Chrome exited before debugging started.');
      await pause(100);
    }
    const port = fs.readFileSync(portFile, 'utf8').split('\n')[0];
    const tabs = await (await fetch(`http://127.0.0.1:${port}/json`)).json();
    socket = new WebSocket(tabs.find(tab => tab.type === 'page').webSocketDebuggerUrl);
    await new Promise((resolve, reject) => { socket.onopen = resolve; socket.onerror = reject; });
    let sequence = 0;
    const waiting = new Map();
    socket.onmessage = event => {
      const message = JSON.parse(event.data);
      if (waiting.has(message.id)) {
        const {resolve, reject} = waiting.get(message.id);
        waiting.delete(message.id);
        message.error ? reject(new Error(JSON.stringify(message.error))) : resolve(message.result);
      }
    };
    send = (method, params = {}) => new Promise((resolve, reject) => {
      const id = ++sequence;
      const timer = setTimeout(() => { waiting.delete(id); reject(new Error('Timed out: ' + method)); }, 15000);
      waiting.set(id, {resolve: result => { clearTimeout(timer); resolve(result); },
                       reject: error => { clearTimeout(timer); reject(error); }});
      socket.send(JSON.stringify({id, method, params}));
    });
    const evaluate = async expression => {
      const result = await send('Runtime.evaluate', {expression, returnByValue: true, awaitPromise: true});
      if (result.exceptionDetails) throw new Error(result.exceptionDetails.exception?.description || result.exceptionDetails.text);
      return result.result.value;
    };
    const until = async expression => {
      for (let i = 0; i < 100; i++) {
        if (await evaluate(expression)) return;
        await pause(100);
      }
      throw new Error('Page did not reach expected state: ' + expression);
    };
    const navigate = async route => {
      await send('Page.navigate', {url: config.base + route});
      await until(`location.pathname + location.search === ${JSON.stringify(route)} && document.readyState === 'complete'`);
    };
    const fill = async data => evaluate(`(() => {
      for (const [name, value] of Object.entries(${JSON.stringify(data)})) {
        const fields = [...document.getElementsByName(name)];
        if (!fields.length) throw new Error('Missing field: ' + name);
        for (const field of fields) {
          if (field.type === 'checkbox' || field.type === 'radio') {
            field.checked = Array.isArray(value) ? value.includes(field.value) : value === 'on' || value === true || value === field.value;
          } else field.value = value;
          field.dispatchEvent(new Event('change', {bubbles: true}));
        }
      }
      return true;
    })()`);
    const capture = async name => {
      await send('Emulation.setDeviceMetricsOverride', {width: 1280, height: 900, deviceScaleFactor: 1, mobile: false});
      await pause(100);
      if (await evaluate('document.documentElement.scrollWidth > innerWidth + 1')) throw new Error(name + ' desktop overflow');
      const image = await send('Page.captureScreenshot', {format: 'png', captureBeyondViewport: true});
      fs.writeFileSync(path.join(directory, name + '.png'), Buffer.from(image.data, 'base64'));
      await send('Emulation.setDeviceMetricsOverride', {width: 390, height: 844, deviceScaleFactor: 1, mobile: true});
      await pause(100);
      if (await evaluate('document.documentElement.scrollWidth > innerWidth + 1')) throw new Error(name + ' mobile overflow');
      await send('Emulation.setDeviceMetricsOverride', {width: 1280, height: 900, deviceScaleFactor: 1, mobile: false});
    };
    const admin = () => send('Network.setCookie', {name: 'sessionid', value: config.adminSession,
                                                   url: config.base, httpOnly: true, sameSite: 'Lax'});
    const submit = () => evaluate("document.querySelector('form.record-editor').requestSubmit(); true");
    const checkNumbers = async () => {
      const result = await evaluate(`(() => {
        const inputs = [...document.querySelectorAll('[data-registration-number]')];
        if (!inputs.length) return false;
        return inputs.every(input => {
          input.value = '001234'; input.dispatchEvent(new Event('input', {bubbles: true}));
          const keyBlocked = !input.dispatchEvent(new KeyboardEvent('keydown', {key: 'e', bubbles: true, cancelable: true}));
          const beforeBlocked = !input.dispatchEvent(new InputEvent('beforeinput', {data: 'abc', inputType: 'insertText', bubbles: true, cancelable: true}));
          const paste = new DataTransfer(); paste.setData('text/plain', 'ID123');
          const pasteBlocked = !input.dispatchEvent(new ClipboardEvent('paste', {clipboardData: paste, bubbles: true, cancelable: true}));
          input.value = 'ID123'; input.dispatchEvent(new Event('input', {bubbles: true}));
          const restored = input.value === '001234';
          const valid = input.checkValidity();
          input.value = ''; input.dispatchEvent(new Event('input', {bubbles: true}));
          return keyBlocked && beforeBlocked && pasteBlocked && restored && valid;
        });
      })()`);
      if (!result) throw new Error('Numeric field typing, paste, zero preservation or validation failed.');
      await evaluate("document.querySelector('[name=contact_number]').focus(); true");
      await send('Input.insertText', {text: 'letters'});
      if (await evaluate("document.querySelector('[name=contact_number]').value !== ''")) throw new Error('Typed letters were accepted.');
    };
    await send('Page.enable');
    await navigate(config.guidance);
    await capture('services');
    await navigate(config.routes.registration_apply);
    await checkNumbers();
    await fill(config.association);
    await capture('association-form');
    await submit();
    await until(`location.pathname === ${JSON.stringify(config.routes.registration_receipt)} && document.readyState === 'complete'`);
    await capture('association-receipt');
    const associationCode = await evaluate("document.querySelector('#registration-reference').innerText.trim()");
    if (!/^AMR-\d{6,}$/.test(associationCode)) throw new Error('Association receipt has no short reference.');
    await admin();
    await navigate(config.routes.review_home);
    await capture('membership-reviews');
    await navigate(config.routes.registration_inbox);
    const associationDetail = await evaluate("[...document.querySelectorAll('a')].map(a=>a.getAttribute('href')).find(h=>h && h.includes('/registrations/AMR-') && h.endsWith('/'))");
    if (!associationDetail) throw new Error('Submitted Association record missing from Admin.');
    for (const query of [associationCode, associationCode.split('-')[1], associationDetail.split('/').filter(Boolean).at(-1)]) {
      await navigate(config.routes.registration_inbox + '?q=' + encodeURIComponent(query));
      if (!(await evaluate('document.body.innerText.includes(' + JSON.stringify(associationCode) + ')'))) throw new Error('Association reference search failed.');
    }
    await navigate(associationDetail);
    if (await evaluate("document.querySelector('[name=assigned_member_number]') !== null")) throw new Error('A separate member-number assignment is still present.');
    if (await evaluate("document.querySelector('[name=pwd_number]').value") !== config.association.pwd_number) throw new Error('The submitted PWD No. was not loaded for review.');
    await capture('association-review');
    await evaluate("document.querySelector('[value=approve_registration]').click(); true");
    await until("document.body.innerText.includes('This applicant is now a member')");
    for (const query of [config.program.reference, config.program.reference.split('-')[1], config.program.original]) {
      await navigate(config.program.url + '?q=' + encodeURIComponent(query));
      if (!(await evaluate('document.body.innerText.includes(' + JSON.stringify(config.program.reference) + ')'))) throw new Error('Program reference search failed.');
    }
    await capture('program-references');
    await send('Network.clearBrowserCookies');
    await navigate(config.routes.pdao_apply);
    if (await evaluate("document.querySelector('[name=submission_channel]') !== null")) throw new Error('PDAO still asks applicants for a submission channel.');
    await checkNumbers();
    await fill(config.pdao);
    await capture('pdao-form');
    await submit();
    await until(`location.pathname === ${JSON.stringify(config.routes.pdao_receipt)} && document.readyState === 'complete'`);
    await capture('pdao-receipt');
    await admin();
    await navigate(config.routes.pdao_inbox);
    await capture('pdao-inbox');
    const pdaoDetail = await evaluate("document.querySelector('tbody a').getAttribute('href')");
    const pdaoCode = await evaluate("document.querySelector('tbody').innerText.match(/PDAO-\\d{6,}/)?.[0]");
    if (!pdaoCode) throw new Error('PDAO inbox has no short reference.');
    for (const query of [pdaoCode, pdaoCode.split('-')[1], 'PDAO-' + pdaoDetail.split('/').filter(Boolean).at(-1)]) {
      await navigate(config.routes.pdao_inbox + '?q=' + encodeURIComponent(query));
      if (!(await evaluate('document.body.innerText.includes(' + JSON.stringify(pdaoCode) + ')'))) throw new Error('PDAO reference search failed.');
    }
    await navigate(pdaoDetail);
    if (!(await evaluate("document.querySelector('#pdao-review-form') !== null"))) throw new Error('Admin cannot edit the PDAO application.');
    await fill({first_name: 'Reviewed', contact_number: '09170000003'});
    await evaluate("document.querySelector('#pdao-review-form button[type=submit]').click(); true");
    await until("document.body.innerText.includes('Reviewed PDAO details saved') && document.readyState === 'complete'");
    if (await evaluate("document.querySelector('[name=first_name]').value") !== 'Reviewed') throw new Error('PDAO correction was not retained.');
    await capture('pdao-review');
    const printURL = await evaluate("document.querySelector('a[href$=\"/print/\"]').getAttribute('href')");
    await navigate(printURL);
    if (!(await evaluate("document.body.innerText.includes('Reviewed Example') && document.body.innerText.includes('09170000003')"))) throw new Error('PDAO printout does not use reviewed details.');
    await capture('pdao-print');
    const buttonWorks = await evaluate("(() => {window.print=()=>window.syntheticPrintCalled=true; document.querySelector('[data-registration-print]').click(); return window.syntheticPrintCalled === true;})()");
    if (!buttonWorks) throw new Error('Print button did not invoke browser printing.');
    const pdf = await send('Page.printToPDF', {printBackground: true, preferCSSPageSize: true, displayHeaderFooter: false});
    fs.writeFileSync(path.join(directory, 'pdao-form.pdf'), Buffer.from(pdf.data, 'base64'));
    await navigate(pdaoDetail);
    await evaluate("document.querySelector('#pdao-forward-form button[type=submit]').click(); true");
    await until("document.querySelector('[name=confirmed]') !== null");
    await fill({confirmed: 'on'});
    await evaluate("document.querySelector('#pdao-forward-form button[type=submit]').click(); true");
    await until("document.body.innerText.includes('Forwarded to PDAO') && !document.querySelector('[name=confirmed]')");
    fs.writeFileSync(path.join(directory, 'result.json'), JSON.stringify({associationApproved: true,
      pdaoForwarded: true, pdaoReviewEditing: true, automaticOnlineChannel: true, shortAndOriginalReferenceSearch: true, printButton: true, desktopAndMobileOverflow: false}, null, 2));
    console.log('Chrome passed: applicant confirmation, Admin Association approval, separate PDAO review/printing/forwarding, desktop and mobile layouts. Artifacts: ' + directory);
  } finally {
    if (send) { try { await send('Browser.close'); } catch {} }
    socket?.close();
    if (child.exitCode === null) child.kill();
    fs.writeFileSync(path.join(directory, 'chrome.log'), log);
  }
})().catch(error => {console.error(error); process.exitCode = 1;});
