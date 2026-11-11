const {chromium}=require(process.env.PLAYWRIGHT_MODULE || 'C:/Users/rovic/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const origin=process.env.PUBLIC_QA_ORIGIN || 'http://127.0.0.1:8013';
const output='docs/admin-login-neutral-2026-11-08';
(async()=>{
  const browser=await chromium.launch({headless:true,executablePath:process.env.CHROME_EXECUTABLE || 'C:/Program Files/Google/Chrome/Application/chrome.exe'});
  try {
    fs.mkdirSync(output,{recursive:true});
    const page=await browser.newPage();
    const errors=[],checks=[];
    page.on('pageerror',error=>errors.push(error.message));
    for(const width of [1440,1024,768,390,320]) {
      await page.setViewportSize({width,height:900});
      assert.equal((await page.goto(origin+'/accounts/login/?next=/dashboard/')).status(),200);
      assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));
      assert.equal(await page.locator('.signin-form').getAttribute('method'),'post');
      assert.equal(await page.locator('.signin-form').getAttribute('action'),'/accounts/login/');
      assert.equal(await page.locator('[name=next]').inputValue(),'/dashboard/');
      assert(await page.locator('[name=csrfmiddlewaretoken]').inputValue());
      assert.equal(await page.locator('#id_password').getAttribute('type'),'password');
      for(const field of ['username','password']) {
        assert(await page.locator(`label[for=id_${field}]`).isVisible());
        assert(await page.locator(`#id_${field}`).isVisible());
      }
      await page.locator('#id_username').focus();
      await page.keyboard.press('Tab');
      assert(await page.locator('#id_password').evaluate(el=>el===document.activeElement));
      await page.keyboard.press('Tab');
      assert(await page.locator('.signin-submit').evaluate(el=>el===document.activeElement));
      await page.evaluate(()=>{document.activeElement.blur();scrollTo(0,0);});
      await page.screenshot({path:`${output}/login-${width}.png`,fullPage:true});
      checks.push({width,labels:true,keyboard:true,noOverflow:true});
    }
    // Inspect a generic server-error presentation without failed live login attempts.
    await page.locator('.signin-form').evaluate(el=>el.insertAdjacentHTML('afterbegin','<div class="alert alert-danger signin-error" role="alert"><ul class="errorlist nonfield"><li>Unable to sign in. Check your credentials or try again later.</li></ul></div>'));
    assert(await page.locator('.signin-error').isVisible());
    assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));
    await page.screenshot({path:`${output}/error-320.png`,fullPage:true});
    await page.locator('.display-trigger').click();
    await page.locator('[data-preference=text]').selectOption('largest');
    await page.locator('[data-preference=contrast]').check();
    await page.locator('.display-close').click();
    await page.evaluate(()=>document.documentElement.style.fontSize='200%');
    assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));
    await page.screenshot({path:`${output}/large-text-high-contrast-320.png`,fullPage:true});
    await page.evaluate(()=>{localStorage.removeItem('santolan-display');});
    const plain=await browser.newPage({javaScriptEnabled:false,viewport:{width:390,height:844}});
    await plain.goto(origin+'/accounts/login/');
    assert(await plain.locator('#id_username').isVisible());
    assert(await plain.locator('.signin-submit').isVisible());
    await plain.close();
    // One successful sign-in checks the retained redirect and authenticated page actions.
    const login=fs.readFileSync('.local/ewaf-twelve-demo/LOGIN.txt','utf8');
    await page.setViewportSize({width:1440,height:960});
    await page.goto(origin+'/accounts/login/?next=/dashboard/');
    await page.locator('#id_username').fill(login.match(/^Username:\s*(.+)$/m)[1].trim());
    await page.locator('#id_password').fill(login.match(/^Password:\s*(.+)$/m)[1].trim());
    await page.locator('.signin-submit').click();
    await page.waitForURL(origin+'/dashboard/');
    await page.goto(origin+'/accounts/login/');
    assert(await page.getByRole('link',{name:'Open your workspace'}).isVisible());
    assert.equal(await page.locator('.signin-logout').getAttribute('method'),'post');
    await page.screenshot({path:`${output}/already-signed-in.png`,fullPage:true});
    await page.getByRole('button',{name:'Sign out',exact:true}).click();
    await page.goto(origin+'/accounts/login/');
    assert(await page.locator('#id_password').isVisible());
    assert.deepEqual(errors,[]);
    fs.writeFileSync(`${output}/results.json`,JSON.stringify({checks,errors,syntheticErrorLayout:true,largeTextHighContrast:true,noJavaScript:true,successfulSignInAndLogout:true},null,2));
    console.log('Five viewport checks, keyboard access, error layout, large text, no-JavaScript and actual sign-in/logout passed.');
  } finally {await browser.close();}
})().catch(error=>{console.error(error);process.exitCode=1;});
