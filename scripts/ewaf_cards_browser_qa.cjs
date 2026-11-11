const fs=require('fs'), path=require('path'), assert=require('assert/strict');
const {chromium}=require(process.env.PLAYWRIGHT_MODULE || path.join(process.env.USERPROFILE,
    '.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright'));
(async()=>{
    const expected=JSON.parse(process.env.QA_EWAF_CARDS);
    const browser=await chromium.launch({headless:true, executablePath:process.env.CHROME_EXECUTABLE});
    try {
        const context=await browser.newContext({viewport:{width:1440,height:1050},reducedMotion:'reduce'});
        await context.addCookies([{name:process.env.QA_COOKIE_NAME,value:process.env.QA_SESSION,url:process.env.QA_URL}]);
        const page=await context.newPage(), errors=[];
        page.on('pageerror',e=>errors.push(e.message));
        page.on('console',m=>{if(m.type()==='error')errors.push(m.text());});
        page.on('response',r=>{if(r.status()>=500)errors.push(r.url());});
        const go=async route=>assert.equal((await page.goto(process.env.QA_URL+route,{waitUntil:'networkidle'})).status(),200);
        const apply=async()=>{await page.getByRole('button',{name:'Apply filters',exact:true}).click();await page.waitForLoadState('networkidle');};
        await go('/ewaf/');
        assert.equal(await page.locator('#program-type,#program-status,#program-registration,#program-applicants').count(),0);
        assert.equal(await page.locator('.program-card-dates,.program-category,.program-configuration-status').count(),0);
        for(const data of expected) {
            const card=page.locator(`.ewaf-program-card[data-program="${data.id}"]`);
            assert.equal(await card.count(),1);
            assert.equal((await card.locator('h2').innerText()).trim(),data.name);
            assert.equal(await card.locator(`.ewaf-state-${data.state}`).count(),1);
            assert.equal(await card.locator('.ewaf-card-weight').count(),4);
            for(const row of data.weights) {
                const weight=card.locator(`[data-criterion="${row.code}"]`);
                if(row.percent===null) assert.equal(await weight.locator('progress').count(),0);
                else {
                    assert.equal(await weight.locator('progress').getAttribute('value'),row.percent);
                    assert.equal(await weight.locator('strong').innerText(),row.percent+'%');
                }
            }
            for(const code of ['total','eligible','pending']) assert.equal(await card.locator(`[data-count="${code}"]`).innerText(),String(data[code]));
            assert.ok((await card.locator('.capacity-heading').innerText()).includes(`${data.used} / ${data.slots ?? 'Not set'}`));
            assert.equal(await card.getByRole('link',{name:'Open EWAF',exact:true}).count(),1);
            assert.equal(await card.locator('a').count(),1);
        }
        await page.screenshot({path:path.join(process.env.QA_OUTPUT,'ewaf-cards-desktop.png')});
        await page.screenshot({path:path.join(process.env.QA_OUTPUT,'ewaf-cards-full.png'),fullPage:true});
        const ready=expected.find(item=>item.state==='ready');
        assert.ok(ready,'A saved authorized configuration is required in this test fixture.');
        await page.getByLabel('Search programs',{exact:true}).fill(ready.code);
        await page.getByLabel('Configuration status',{exact:true}).selectOption('ready');
        await page.getByLabel('Sort by',{exact:true}).selectOption('az');
        await apply();
        assert.equal(await page.locator('.ewaf-program-card').count(),1);
        await page.getByRole('link',{name:'Open EWAF',exact:true}).click();
        await page.waitForLoadState('networkidle');
        assert.equal(new URL(page.url()).pathname,`/ewaf/programs/${ready.id}/`);
        assert.equal(await page.locator('#weight-bars input[type=range]').count(),4);
        assert.ok(await page.getByRole('button',{name:'Generate EWAF',exact:true}).count());
        const capacity=page.getByRole('region',{name:'Beneficiary capacity'});
        assert.ok((await capacity.innerText()).includes(`${ready.used} / ${ready.slots}`));
        await go('/ewaf/?configuration=ready');
        assert.equal(await page.locator('.ewaf-program-card').count(),expected.filter(item=>item.state==='ready').length);
        await page.screenshot({path:path.join(process.env.QA_OUTPUT,'ewaf-cards-ready.png')});
        await page.getByRole('link',{name:'Reset Filters',exact:true}).click();
        await page.waitForLoadState('networkidle');
        assert.equal(await page.locator('#configuration-status').inputValue(),'');
        const newest=await page.locator('.ewaf-program-card h2').allTextContents();
        await page.locator('#program-sort').selectOption('oldest');await apply();
        const oldest=await page.locator('.ewaf-program-card h2').allTextContents();
        assert.deepEqual(oldest.reverse(),newest);
        await go('/ewaf/');
        for(const width of [320,390,768,1024,1440,1680]) {
            await page.setViewportSize({width,height:1050});
            assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth+1),false,`Overflow at ${width}`);
            const columns=await page.locator('.program-grid').evaluate(el=>getComputedStyle(el).gridTemplateColumns.split(' ').length);
            assert.equal(columns,width<700?1:width<1200?2:3);
            if(width===390) {
                await page.screenshot({path:path.join(process.env.QA_OUTPUT,'ewaf-cards-mobile.png'),fullPage:true});
                await page.screenshot({path:path.join(process.env.QA_OUTPUT,'ewaf-cards-mobile-viewport.png')});
            }
        }
        for(const control of await page.locator('main input,main select').all())assert.ok(await control.evaluate(el=>el.labels.length));
        const open=page.getByRole('link',{name:'Open EWAF',exact:true}).first();
        await open.focus();
        await Promise.all([page.waitForURL(url=>url.pathname.startsWith('/ewaf/programs/')),page.keyboard.press('Enter')]);
        await page.waitForLoadState('networkidle');
        assert.ok(new URL(page.url()).pathname.startsWith('/ewaf/programs/'));
        assert.deepEqual(errors,[]);
        fs.writeFileSync(path.join(process.env.QA_OUTPUT,'results.json'),JSON.stringify({passed:true,programs:expected.length,responsive_checks:6,browser_errors:errors},null,2));
        console.log(`PASS: ${expected.length} EWAF cards; saved AHP weights, no active draft weights, exact applicant and capacity counts, filters/sort/reset, correct workspace and keyboard navigation; 6 responsive widths; zero browser errors.`);
    } finally {await browser.close();}
})().catch(error=>{console.error(error);process.exitCode=1;});
