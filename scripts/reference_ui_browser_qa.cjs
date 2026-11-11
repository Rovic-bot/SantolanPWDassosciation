const fs = require('fs'), path = require('path'), assert = require('assert/strict');
const {chromium} = require(process.env.PLAYWRIGHT_MODULE || path.join(process.env.USERPROFILE,
    '.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright'));
(async () => {
    const data = JSON.parse(process.env.QA_REFERENCE);
    const browser = await chromium.launch({headless:true, executablePath:process.env.CHROME_EXECUTABLE});
    try {
        const context = await browser.newContext({viewport:{width:1440,height:1050}, reducedMotion:'reduce',
            permissions:['clipboard-read', 'clipboard-write']});
        await context.addCookies([{name:process.env.QA_COOKIE_NAME,value:process.env.QA_SESSION,url:process.env.QA_URL}]);
        const page = await context.newPage(), errors = [];
        page.on('pageerror', e => errors.push(e.message));
        page.on('console', m => {if (m.type() === 'error') errors.push(m.text());});
        page.on('response', r => {if (r.status() >= 500) errors.push(r.url());});
        const go = async route => assert.equal((await page.goto(process.env.QA_URL+route,{waitUntil:'networkidle'})).status(),200);
        const click = async locator => {await locator.click();await page.waitForLoadState('networkidle');};
        const shot = async name => {
            await page.evaluate(() => scrollTo(0,0));
            await page.screenshot({path:path.join(process.env.QA_OUTPUT,name+'.png'),fullPage:true});
            if (['program-management','program-applications','ewaf-programs','assistance-programs','applicant-detail'].includes(name)) {
                await page.screenshot({path:path.join(process.env.QA_OUTPUT,name+'-desktop.png')});
            }
        };
        const programURL = `/programs/manage/${data.program}/`;
        const applicantsURL = `${programURL}applications/`;
        const applicantURL = `${applicantsURL}${data.application}/`;
        const programPages = [
            {route:'/programs/manage/', action:'View Program', destination:programURL, shot:'program-management'},
            {route:'/workspace/applications/', action:'View Program', destination:applicantsURL, shot:'program-applications'},
            {route:'/assistance/releases/', action:'View Releases', destination:`/assistance/releases/program/${data.program}/`, shot:'assistance-programs'},
        ];
        for (const {route,action,destination,shot:screenshot} of programPages) {
            await go(route);
            assert.ok(await page.locator('.program-reference-card').count() >= 1);
            assert.ok(await page.locator('#program-search').evaluate(el => parseFloat(getComputedStyle(el).paddingLeft) >= 40));
            await page.locator('#program-search').fill(data.code);
            await page.locator('#program-type').selectOption(data.type);
            await page.locator('#program-status').selectOption(data.status);
            await page.locator('#program-sort').selectOption('az');
            await page.locator('#program-applicants').check();
            await click(page.getByRole('button',{name:'Apply filters',exact:true}));
            assert.equal(await page.locator('.program-reference-card').count(),1);
            const card = page.locator('.program-reference-card');
            assert.equal((await card.locator('h2').innerText()).trim(),data.name);
            assert.ok((await card.locator('.capacity-heading').innerText()).includes(`${data.allocated} / ${data.slots}`));
            assert.ok((await card.locator('.capacity-foot').innerText()).includes(`Applicants: ${data.applicants}`));
            const openProgram = card.getByRole('link',{name:action,exact:true});
            assert.equal(await openProgram.getAttribute('href'),destination);
            const filteredURL = page.url();
            await click(openProgram);
            assert.equal(new URL(page.url()).pathname,destination);
            assert.equal((await page.goto(filteredURL,{waitUntil:'networkidle'})).status(),200);
            await click(page.getByRole('link',{name:'Reset Filters',exact:true}));
            assert.equal(await page.locator('#program-search').inputValue(),'');
            const newest = await page.locator('.program-reference-card h2').allTextContents();
            await page.locator('#program-sort').selectOption('oldest');
            await click(page.getByRole('button',{name:'Apply filters',exact:true}));
            const oldest = await page.locator('.program-reference-card h2').allTextContents();
            if (newest.length < 20) assert.deepEqual(oldest.reverse(),newest);
            await go(route);
            await shot(screenshot);
        }
        await go(applicantsURL);
        await page.locator('#search').fill(data.control);
        await page.locator('#applicant-sort').selectOption('az');
        await click(page.getByRole('button',{name:'Filter',exact:true}));
        assert.equal(await page.locator('tbody tr').count(),1);
        assert.ok((await page.locator('tbody').innerText()).includes(data.reference));
        await go(applicantsURL); await shot('applicant-list');
        await go(applicantURL);
        assert.ok(await page.getByRole('heading',{name:'Member Verification & Details',exact:true}).isVisible());
        for (const [button,value,message] of [
            ['Copy control number',data.control,'Control number copied.'],
            ['Copy application reference',data.reference,'Application reference copied.']]) {
            await page.getByRole('button',{name:button,exact:true}).click();
            await page.waitForFunction(message => document.getElementById('member-copy-status').textContent === message,message);
            assert.equal(await page.evaluate(() => navigator.clipboard.readText()),value);
        }
        const history = page.getByRole('navigation',{name:'Member information sections'}).getByRole('link',{name:'Application History',exact:true});
        await history.focus(); await page.keyboard.press('Enter');
        assert.ok(await page.locator('#application-history').evaluate(node => node.open));
        await page.locator('#application-history').evaluate(node => node.open=false);
        await go(applicantURL);
        await shot('applicant-detail');
        const preview = page.getByRole('link',{name:'Preview',exact:true}).first();
        const previewURL = process.env.QA_URL + await preview.getAttribute('href');
        const file = await context.request.get(previewURL);
        assert.equal(file.status(),200);
        assert.ok(file.headers()['cache-control'].includes('no-store'));
        const anonymous = await browser.newContext();
        const blocked = await anonymous.request.get(previewURL,{maxRedirects:0});
        assert.ok([302,403].includes(blocked.status()));
        await anonymous.close();
        let layouts = 0;
        const programRoutes = programPages.map(item => item.route);
        for (const route of [...programRoutes,programURL,applicantsURL,applicantURL]) {
            await go(route);
            for (const width of [320,390,768,1024,1440,1680]) {
                await page.setViewportSize({width,height:1050});
                assert.equal(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth+1),false,`${route} ${width}`);
                if (programRoutes.includes(route)) {
                    const columns=await page.locator('.program-grid').evaluate(el=>getComputedStyle(el).gridTemplateColumns.split(' ').length);
                    assert.equal(columns,width < 700 ? 1 : width < 1200 ? 2 : 3);
                }
                layouts++;
            }
            await page.setViewportSize({width:1440,height:1050});
            if (route === programURL) await shot('program-detail');
        }
        await page.setViewportSize({width:390,height:1050});
        await go(applicantURL); await shot('applicant-mobile');
        assert.deepEqual(errors,[]);
        const result={passed:true,responsive_checks:layouts,console_errors:errors.length,
            clipboard:true,protected_previews:true,filters:true,correct_slot_usage:true};
        fs.writeFileSync(path.join(process.env.QA_OUTPUT,'browser-result.json'),JSON.stringify(result,null,2));
        console.log(`PASS: three shared program listings, combined filters/code search/sorts/reset, correct workflow destinations, actual slot usage, applicant listing, profile copy controls, keyboard section navigation, private previews, ${layouts} responsive route/width checks; zero browser errors.`);
    } finally {await browser.close();}
})().catch(error=>{console.error(error);process.exitCode=1;});
