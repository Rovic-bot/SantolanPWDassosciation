const assert = require('assert/strict'), path = require('path');
const {chromium} = require(process.env.PLAYWRIGHT_MODULE || path.join(process.env.USERPROFILE,
    '.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright'));
(async () => {
    const browser = await chromium.launch({headless:true, executablePath:process.env.CHROME_EXECUTABLE});
    try {
        const context = await browser.newContext({viewport:{width:1440,height:1050}});
        await context.addCookies([{name:process.env.QA_COOKIE_NAME,value:process.env.QA_SESSION,url:process.env.QA_URL}]);
        const page = await context.newPage(), errors = [];
        page.on('pageerror', error => errors.push(error.message));
        page.on('response', response => {if (response.status() >= 500) errors.push(response.url());});
        const go = async url => assert.equal((await page.goto(process.env.QA_URL + url, {waitUntil:'networkidle'})).status(), 200);
        const submit = async label => {
            await page.getByRole('button',{name:label,exact:true}).click();
            await page.waitForLoadState('networkidle');
        };
        await go('/programs/manage/new/');
        assert.equal(await page.locator('[name="requirements-0-label"]').count(), 0);
        await page.getByLabel('Title:', {exact:true}).fill('Fictional optional requirements browser');
        await page.locator('textarea[name=description]').fill('Fictional program created without extra requirements.');
        await page.locator('[name=registration_opens_at]').fill('2027-05-01T09:00');
        await page.locator('[name=registration_closes_at]').fill('2027-05-10T17:00');
        await page.locator('[name=ewaf_applicable]').uncheck();
        await page.getByLabel('Cancer (RA 11215)',{exact:true}).check();
        await page.getByLabel('Visual Disability',{exact:true}).check();
        await submit('Create program');
        const created = new URL(page.url()).pathname;
        assert.ok(/\/manage\/[a-f0-9-]+\/$/.test(created), await page.locator('main').innerText());
        await page.getByRole('link',{name:'Edit Program',exact:true}).click();
        assert.ok(await page.getByLabel('Cancer (RA 11215)',{exact:true}).isChecked());
        assert.ok(await page.getByLabel('Visual Disability',{exact:true}).isChecked());
        await page.screenshot({path:path.join(process.env.QA_OUTPUT,'program-edit.png'),fullPage:true});
        await go(created);
        const publish = async () => {
            await page.locator('[name=action]').selectOption('published');
            await page.locator('[name=notes]').fill('Fictional notice publication; offline approval must be checked.');
            await page.locator('[name=confirm]').check();
            await submit('Apply program change');
        };
        await publish();
        assert.ok((await page.locator('#error-summary').innerText()).includes('approval covering its current terms'));
        assert.ok(!(await page.locator('#error-summary').innerText()).includes('photo instructions'));
        await go(`/programs/manage/${process.env.QA_PROGRAM}/`);
        await publish();
        assert.equal(await page.locator('#error-summary').count(), 0);
        assert.ok((await page.locator('main').innerText()).includes('Program status updated'));
        await go(`/ewaf/programs/${process.env.QA_SCORING}/`);
        const rawKeys = /authority_reference|authorized_scope|effective_from|SI\.measure|PR\.functional_need|pa_scope/;
        assert.equal(rawKeys.test(await page.locator('main').innerText()), false);
        assert.ok(await page.getByRole('button',{name:'Generate EWAF',exact:true}).isDisabled());
        const [settingsResponse] = await Promise.all([
            page.waitForResponse(response => response.url().includes('?settings=1') && response.request().isNavigationRequest()),
            page.getByRole('link',{name:'Complete Settings',exact:true}).click()
        ]);
        assert.equal(settingsResponse.status(), 200);
        await page.waitForLoadState('networkidle');
        assert.ok(await page.getByLabel('Approval reference:',{exact:true}).isVisible());
        assert.equal(rawKeys.test(await page.locator('main').innerText()), false);
        for (const width of [320,390,768,1440]) {
            await page.setViewportSize({width,height:1050});
            assert.equal(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth + 1), false);
        }
        assert.deepEqual(errors, []);
        console.log('PASS: exact shared program choices saved/reloaded; optional requirements; publication without optional instructions; missing PDAO approval blocked; approved notice published; incomplete EWAF blocked; guided policy labels; responsive settings.');
    } finally {await browser.close();}
})().catch(error => {console.error(error);process.exitCode=1;});
