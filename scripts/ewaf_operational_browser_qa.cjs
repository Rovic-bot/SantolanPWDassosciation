const path = require('path');
const assert = require('assert/strict');
const runtime = path.join(process.env.USERPROFILE, '.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
const {chromium} = require(process.env.PLAYWRIGHT_MODULE || runtime);
(async () => {
  const browser = await chromium.launch({headless:true, executablePath:process.env.CHROME_EXECUTABLE || 'C:/Program Files/Google/Chrome/Application/chrome.exe'});
  try {
    const context = await browser.newContext({viewport:{width:1440,height:1100},reducedMotion:'reduce'});
    await context.addCookies([{name:process.env.QA_COOKIE_NAME,value:process.env.QA_SESSION,url:process.env.QA_URL}]);
    const page = await context.newPage();
    const errors=[];
    page.on('pageerror', error => errors.push(error.message));
    const workspace=`/ewaf/programs/${process.env.QA_PROGRAM}/`;
    async function go(route) {
      const response=await page.goto(process.env.QA_URL+route,{waitUntil:'networkidle'});
      assert.equal(response.status(),200);
      assert.ok(response.headers()['cache-control'].includes('no-store'));
      assert.ok((await page.locator('main').innerText()).includes('Fictional demonstration database'));
    }
    async function shot(name) { await page.screenshot({path:path.join(process.env.QA_OUTPUT,`operational-${name}.png`)}); }
    await go(workspace);
    await page.locator('main').getByRole('link',{name:'Weights',exact:true}).click();
    assert.equal(await page.locator('select[name^="pair_"]').count(),0);
    assert.equal(await page.locator('#weight-bars input[type=range]').count(),4);

    await page.locator('#configuration').getByLabel('Reason').fill('Fictional browser verification of complete rules and dates. This is not Association approval.');
    await page.locator('#configuration [name=attested]').check();
    await page.getByRole('button',{name:'Lock configuration',exact:true}).click();
    await page.waitForLoadState('networkidle');
    assert.ok((await page.locator('main').innerText()).includes('Authorized and locked'));
    await shot('configuration');
    assert.equal(await page.getByText('SI measurement and normalization',{exact:true}).count(),0);
    await go(workspace);
    assert.equal(await page.locator('#readiness table tbody tr').count(),4);
    await shot('eligibility');
    for(let version=1;version<=2;version++) {
      if(version>1) await go(workspace);
      await page.locator('#calculate').getByLabel('Reason').fill(`Fictional complete-pool calculation ${version}; retain predecessor evidence.`);
      await page.getByRole('button',{name:'Generate EWAF',exact:true}).click();
      await page.waitForLoadState('networkidle');
      assert.ok((await page.locator('main').innerText()).includes('Current verified calculation'));
    }
    const resultUrl=new URL(page.url()).pathname;
    const rows=page.locator('#results table tbody tr');
    assert.equal(await rows.count(),4);
    const values=await rows.locator('td:nth-child(3)').allTextContents();
    assert.ok(Number(values[0])>=Number(values[1]) && Number(values[1])>=Number(values[2]));
    await shot('comparison');
    const first=page.locator('#results table tbody tr').first();
    const summary=first.getByText('Record beneficiary decision',{exact:true});
    await summary.focus(); await page.keyboard.press('Enter');
    assert.ok((await page.locator('#results table caption').innerText()).includes('scored eligible applicants'));
    await first.scrollIntoViewIfNeeded();
    await shot('calculation');
    await first.getByLabel('Outcome').selectOption('SELECTED');
    await first.getByLabel('Reason').fill('Fictional human review of functional need, verified evidence and available slots.');
    await first.getByLabel('Application of the approved tie procedure').fill('Fictional documented human assessment; no automatic tie-break.');
    await first.getByRole('button',{name:'Save beneficiary decision',exact:true}).click();
    await page.waitForLoadState('networkidle');
    const secondReview=page.locator('#results table tbody tr').first();
    await secondReview.getByText('Record beneficiary decision',{exact:true}).click();
    await secondReview.getByLabel('Outcome').selectOption('DEFERRED');
    await secondReview.getByLabel('Reason').fill('Fictional follow-up review; preserve previous selection and exact scores.');
    await secondReview.getByRole('button',{name:'Save beneficiary decision',exact:true}).click();
    await page.waitForLoadState('networkidle');
    const history=page.locator('details').filter({has:page.locator('summary').filter({hasText:/^Decision history$/})});
    await history.locator('summary').click();
    assert.equal(await history.locator('p').count(),2);
    await shot('decisions');
    await go(workspace);
    assert.equal(await page.getByRole('heading',{name:'Calculation and recalculation history',exact:true}).count(),0);
    assert.equal(await page.getByRole('heading',{name:'Results and human selection',exact:true}).count(),1);
    await shot('history');
    for(const route of [workspace,workspace+'configuration/',resultUrl]) {
      await go(route);
      for(const width of [320,390,768,1440]) {
        await page.setViewportSize({width,height:1000});
        assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth+1),false,`${route} ${width}`);
      }
      assert.equal(await page.locator('main h1').count(),1);
      assert.equal(await page.locator('[name="score"], [name="rank"], [name="weights"]').count(),0);
      for(const input of await page.locator('main input:not([type="hidden"]), main select, main textarea').all()) {
        assert.ok(await input.evaluate(el=>el.labels && el.labels.length));
      }
    }
    await page.setViewportSize({width:390,height:1000}); await shot('mobile');
    assert.deepEqual(errors,[]);
    console.log('Operational Admin browser passed: locked AHP policy through current slider interface, four verified applicants, ranked scores, two calculations, two reasoned human revisions, private/no-store, keyboard labels and 320/390/768/1440 widths.');
  } finally {await browser.close();}
})().catch(error=>{console.error(error);process.exit(1);});
