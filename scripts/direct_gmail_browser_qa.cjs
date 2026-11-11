const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const {chromium} = require(process.env.PLAYWRIGHT_MODULE || path.join(process.env.USERPROFILE,
  '.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright'));

(async () => {
  const browser = await chromium.launch({headless:true,
    executablePath:process.env.CHROME_EXECUTABLE || 'C:/Program Files/Google/Chrome/Application/chrome.exe'});
  const base = process.env.QA_URL, output = process.env.QA_OUTPUT, errors = [];
  try {
    const context = await browser.newContext({viewport:{width:1440,height:1000}, reducedMotion:'reduce'});
    await context.addCookies([{name:'sessionid',value:process.env.QA_SESSION,url:base}]);
    await context.route('**/*', route => new URL(route.request().url()).origin === new URL(base).origin
      ? route.continue() : route.abort());
    const page = await context.newPage();
    page.on('pageerror', error => errors.push(error.message));
    await page.goto(base + process.env.QA_INBOX);
    await page.getByRole('link',{name:'Association email settings',exact:true}).click();
    assert.match(await page.locator('main').textContent(), /Gmail is not connected/);
    assert.equal(await page.locator('[name=gmail_app_password]').getAttribute('type'), 'password');
    for (const sender of ['first@example.invalid','second@example.invalid']) {
      await page.goto(base + process.env.QA_SETTINGS);
      await page.locator('[name=sender_email]').fill(sender);
      await page.locator('[name=gmail_app_password]').fill('abcd efgh ijkl mnop');
      await page.locator('[name=reason]').fill('Synthetic account connection for browser validation.');
      await page.getByRole('button',{name:'Save Association email',exact:true}).click();
      await page.getByText('Email connection configured.',{exact:true}).waitFor();
      assert.equal(await page.locator('[name=gmail_app_password]').inputValue(), '');
      assert.doesNotMatch(await page.content(), /abcdefghijklmnop|abcd efgh ijkl mnop/);
      if (sender.startsWith('first')) {
        for (const width of [1440,390]) {
          await page.setViewportSize({width,height:1000});
          assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1));
          await page.screenshot({path:path.join(output,`settings-${width}.png`),fullPage:true});
        }
      }
      await page.setViewportSize({width:1440,height:1000});
      await page.goto(base + process.env.QA_INBOX);
      await page.getByRole('link',{name:'View ticket',exact:true}).click();
      const dialog = page.locator('#record-details-dialog');
      await page.waitForFunction(() => !document.querySelector('[data-referral-open]') && document.querySelector('[data-referral-reply]'));
      assert.equal(await dialog.locator('[data-record-full-page]').count(),0,'Tickets have no full-page link');
      assert.equal(await dialog.getByRole('button',{name:'Close record',exact:true}).isVisible(),true);
      const form = dialog.locator('[data-referral-reply]');
      assert.match(await form.locator('[name=channel]').textContent(), new RegExp(sender.replace('.', '\\.')));
      assert.equal(await form.locator('[name=channel]').inputValue(),'email');
      assert.equal(await dialog.locator('[data-gmail-compose], [name=email_app_sent]').count(), 0);
      await form.locator('[name=member_message]').fill('A synthetic reply typed inside the system.');
      await form.locator('[name=notes]').fill('Private staff note.');
      const version = await form.locator('[name=version]').inputValue();
      await form.getByRole('button',{name:'Send reply',exact:true}).click();
      await page.waitForFunction(previous => document.querySelector('[data-referral-reply] [name=version]')?.value !== previous, version);
      await dialog.getByText('Accepted by email service',{exact:true}).first().waitFor();
      assert.equal(context.pages().length, 1);
      await page.screenshot({path:path.join(output,`reply-${sender.split('@')[0]}.png`)});
    }
    await page.goto(base + process.env.QA_SETTINGS);
    await page.locator('[name=sender_email]').fill('disconnected@example.invalid');
    await page.locator('[name=reason]').fill('Synthetic address-only change.');
    await page.getByRole('button',{name:'Save Association email',exact:true}).click();
    await page.getByText(/Gmail is not connected/).waitFor();
    await page.goto(base + process.env.QA_INBOX);
    await page.getByRole('link',{name:'View ticket',exact:true}).click();
    const form = page.locator('[data-referral-reply]');
    await form.waitFor();
    const version = await form.locator('[name=version]').inputValue();
    await form.locator('[name=member_message]').fill('This must not be sent.');
    await form.locator('[name=notes]').fill('Private staff note.');
    await form.getByRole('button',{name:'Send reply',exact:true}).click();
    await page.getByText('Connect this Gmail account in Association email settings before sending.',{exact:true}).waitFor();
    assert.equal(await page.locator('[data-referral-reply] [name=version]').inputValue(), version);
    assert.equal(await page.locator('[name=member_message]').inputValue(),'This must not be sent.');
    // Ticket retry/session feedback must not refer to the removed link.
    await page.goto(base + process.env.QA_INBOX);
    const ticketOpener = page.getByRole('link',{name:'View ticket',exact:true});
    const ticketUrl = new URL(await ticketOpener.getAttribute('href'),base).href;
    await page.route(ticketUrl,route=>route.fulfill({status:503,body:'Synthetic unavailable response'}));
    await ticketOpener.click();
    const ticketDialog = page.locator('#record-details-dialog');
    await ticketDialog.getByRole('alert').waitFor();
    assert.doesNotMatch(await ticketDialog.textContent(), /Open full page|Full view/i);
    await page.unroute(ticketUrl);
    await ticketDialog.getByRole('button',{name:'Reload details',exact:true}).click();
    await ticketDialog.locator('[data-referral-reply]').waitFor();
    await page.setViewportSize({width:390,height:900});
    assert.ok(await ticketDialog.locator('[data-record-dialog-content]').evaluate(n=>n.scrollWidth<=n.clientWidth+1));
    await page.screenshot({path:path.join(output,'ticket-without-full-view-mobile.png')});
    await page.keyboard.press('Escape');
    assert.equal(await ticketDialog.isVisible(),false);
    assert.equal(await ticketOpener.evaluate(n=>n===document.activeElement),true);
    await page.setViewportSize({width:1440,height:1000});
    await page.route(ticketUrl,route=>route.fulfill({status:200,contentType:'text/html',body:'<h1>Sign in</h1>'}));
    await ticketOpener.click();
    await ticketDialog.getByRole('alert').waitFor();
    assert.doesNotMatch(await ticketDialog.textContent(), /Open full page|Full view/i);
    assert.match(await ticketDialog.textContent(), /sign in again/);
    await page.unroute(ticketUrl);
    await ticketDialog.getByRole('button',{name:'Reload details',exact:true}).click();
    await ticketDialog.locator('[data-referral-reply]').waitFor();
    await page.screenshot({path:path.join(output,'ticket-without-full-view-desktop.png')});
    await ticketDialog.getByRole('button',{name:'Close record',exact:true}).click();
    // The shared dialog retains the full-page option for member records.
    await page.goto(base + process.env.QA_MEMBERS);
    await page.locator('[data-preview-full]').click();
    const memberDialog = page.locator('#record-details-dialog');
    await memberDialog.locator('[data-record-content]').waitFor();
    assert.equal(await memberDialog.locator('[data-record-full-page]').isVisible(),true);
    assert.match(await memberDialog.locator('[data-record-full-page]').getAttribute('href'), /members/);
    assert.deepEqual(errors,[]);
    fs.writeFileSync(path.join(output,'results.json'),JSON.stringify({errors,checks:
      'Connect/change account; encrypted-secret field never echoed; direct replies in same tab; actual sender from settings; disconnected sending blocked; mobile/desktop settings layout; provider mocked; ticket full-page link absent; retry/session errors, close/Escape/focus return; member full-page link retained'},null,2));
    console.log('PASS: settings connection, two senders, direct popup replies, disconnected guard, desktop/mobile.');
  } finally { await browser.close(); }
})().catch(error => {console.error(error);process.exitCode=1;});
