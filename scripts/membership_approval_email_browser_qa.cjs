const assert = require('node:assert/strict');
const path = require('node:path');
const {chromium} = require(process.env.PLAYWRIGHT_MODULE || path.join(process.env.USERPROFILE,
  '.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright'));
(async () => {
  const browser = await chromium.launch({headless:true, executablePath:process.env.CHROME_EXECUTABLE || 'C:/Program Files/Google/Chrome/Application/chrome.exe'});
  try {
    const page = await browser.newPage({viewport:{width:1440,height:1000}});
    const errors = [];
    page.on('pageerror', e => errors.push(e.message));
    await page.goto(process.env.QA_URL + process.env.QA_PUBLIC_ROUTE);
    for (const name of ['email','pwd_number']) assert(await page.locator(`[name=${name}]`).evaluate(el=>el.required && el.validity.valueMissing));
    await page.locator('[data-registration-privacy-open]').click();
    await page.locator('[data-registration-privacy-close]').click();
    for (const [name,value] of Object.entries(JSON.parse(process.env.QA_FORM_DATA))) {
      const field = page.locator(`[name="${name}"]`);
      if (await field.evaluate(el=>el.type === 'checkbox')) await field.check();
      else if (await field.evaluate(el=>el.tagName === 'SELECT')) await field.selectOption(value);
      else await field.fill(value);
    }
    await page.locator('[name=email]').scrollIntoViewIfNeeded();
    await page.screenshot({path:path.join(process.env.QA_OUTPUT,'online-email-required.png')});
    await page.getByRole('button',{name:'Confirm details and submit application',exact:true}).click();
    await page.getByRole('heading',{name:'Registration submitted',exact:true}).waitFor();
    const reference = (await page.locator('#registration-reference').innerText()).trim();
    assert(await page.getByRole('heading',{name:'Wait for Admin review and check your email'}).isVisible());
    const admin = await browser.newContext({viewport:{width:1440,height:1000},reducedMotion:'reduce'});
    await admin.addCookies([{name:'sessionid',value:process.env.QA_ADMIN_SESSION,url:process.env.QA_URL}]);
    await admin.route('https://registry.example.test/**', route=>route.fulfill({body:'Synthetic PRPWD stand-in'}));
    const review = await admin.newPage();
    review.on('pageerror', e=>errors.push(e.message));
    await review.goto(process.env.QA_URL + process.env.QA_LOOKUP_ROUTE + '?reference=' + encodeURIComponent(reference));
    const approve = review.locator('[value=approve_registration]');
    assert(await approve.isDisabled());
    await review.getByRole('button',{name:'Send office-verification email',exact:true}).click();
    await review.locator('#office-verification-email').waitFor();
    assert.match(await review.locator('#office-verification-email').innerText(), /Saved to test outbox/);
    assert.match(await review.locator('#office-verification-email').innerText(), /not yet a member/);
    for (const width of [1440,390,320]) {
      await review.setViewportSize({width,height:1000});
      assert(await review.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));
      await review.locator('#office-verification-email').scrollIntoViewIfNeeded();
      await review.waitForTimeout(250); // Let responsive glass layers finish repainting before capture.
      await review.screenshot({path:path.join(process.env.QA_OUTPUT,`office-invitation-${width}.png`)});
    }
    await review.setViewportSize({width:1440,height:1000});
    const popup = review.waitForEvent('popup');
    await review.locator('[data-prpwd-open]').click();
    await (await popup).close();
    assert(await approve.isDisabled());
    await review.locator('[name=office_verification_confirmed]').check();
    assert(await approve.isEnabled());
    await approve.click();
    await review.locator('#membership-approval-email').waitFor();
    assert.match(await review.locator('#membership-approval-email').innerText(),/Saved to test outbox/);
    assert.match(await review.locator('#membership-approval-email').innerText(),/You are now a member/);
    for (const width of [1440,390,320]) {
      await review.setViewportSize({width,height:1000});
      assert(await review.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));
      await review.locator('#membership-approval-email').scrollIntoViewIfNeeded();
      await review.screenshot({path:path.join(process.env.QA_OUTPUT,`approval-email-${width}.png`)});
    }
    await review.reload();
    assert.equal(await review.getByRole('button',{name:'Retry approval email',exact:true}).count(),0);
    assert.deepEqual(errors,[]);
    console.log('Online submission, pending office invitation, required office-verification confirmation, manual PRPWD, final approval and membership email passed at three responsive widths.');
  } finally {await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
