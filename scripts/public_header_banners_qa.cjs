/* Read-only public header and unsaved CMS preview checks. */
const { chromium } = require(process.env.PLAYWRIGHT_MODULE || 'C:/Users/rovic/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const origin = process.env.PUBLIC_QA_ORIGIN || 'http://127.0.0.1:8013';
const output = 'docs/public-header-banners-2026-11-08';
(async () => {
  const browser = await chromium.launch({headless:true,executablePath:process.env.CHROME_EXECUTABLE || 'C:/Program Files/Google/Chrome/Application/chrome.exe'});
  try {
    fs.mkdirSync(output,{recursive:true});
    const page = await browser.newPage({viewport:{width:1440,height:960}});
    const errors=[], checks=[];
    page.on('pageerror',e=>errors.push(e.message));
    await page.goto(origin);
    const routes=await page.locator('.portal-navigation-links a').evaluateAll(links=>links.map(link=>({label:link.getAttribute('aria-label'),path:new URL(link.href).pathname})));
    assert.equal(routes.length,7);
    for(const width of [1440,768,390,320]) {
      await page.setViewportSize({width,height:960});
      for(const {label,path} of routes) {
        assert.equal((await page.goto(origin+path)).status(),200);
        const header=page.locator('.section-photo-banner, .home-landing').first();
        const img=header.locator('.section-banner-art img, :scope > img').first();
        await img.evaluate(image=>image.decode());
        assert(await header.locator('h1').isVisible());
        assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));
        assert(await header.evaluate(el=>{const r=el.getBoundingClientRect(),h=el.querySelector('h1').getBoundingClientRect();return h.left>=r.left && h.right<=r.right && h.bottom<=r.bottom;}));
        if(path!=='/') {
          assert(await header.locator('.section-banner-shade').isVisible());
          assert.equal(await header.evaluate(el=>getComputedStyle(el,'::after').display),'none');
        }
        if([1440,390].includes(width)) await header.screenshot({path:`${output}/${path.split('/')[1] || 'home'}-${width}.png`});
        checks.push({label,width,imageLoaded:true,headingVisible:true});
      }
      console.log(`Seven tab headers checked at ${width}px`);
    }
    await page.setViewportSize({width:1440,height:960});
    await page.goto(origin+'/programs/');
    await page.evaluate(()=>window.headerCheck=true);
    await page.locator('.catalog-tab').filter({hasText:/^Open/}).click();
    await page.waitForFunction(()=>document.querySelector('.public-browse-status')?.textContent==='Results updated.');
    assert(await page.evaluate(()=>window.headerCheck));
    await page.locator('.section-banner-art img').evaluate(img=>img.decode());
    const login=fs.readFileSync('.local/ewaf-twelve-demo/LOGIN.txt','utf8');
    await page.goto(origin+'/accounts/login/');
    await page.locator('[name=username]').fill(login.match(/^Username:\s*(.+)$/m)[1].trim());
    await page.locator('[name=password]').fill(login.match(/^Password:\s*(.+)$/m)[1].trim());
    await page.locator('button[type=submit]').click();
    await page.goto(origin+'/content/');
    const frame=page.frameLocator('[data-editor-frame]');
    for(const key of ['about','announcements','events','programs','membership','resources']) {
      await page.locator(`[data-editor-page=${key}]`).click();
      await frame.locator('.section-banner-art [data-portal-picture=hero_picture] .portal-picture-action').click();
      await page.locator('[data-editor-picture-dialog][open]').waitFor();
      await page.keyboard.press('Escape');
      assert.equal(await frame.locator('[data-portal-field=hero_title]').getAttribute('contenteditable'),'plaintext-only');
    }
    assert.deepEqual(errors,[]);
    fs.writeFileSync(`${output}/results.json`,JSON.stringify({checks,errors,adminImageControls:true,programFilterWithoutReload:true,contentSaved:false},null,2));
    console.log('All photo headers, in-place program filters and six CMS image controls passed. No content saved.');
  } finally {await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
