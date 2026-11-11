const fs = require('fs'), path = require('path'), assert = require('assert/strict');
const {chromium} = require(process.env.PLAYWRIGHT_MODULE || path.join(process.env.USERPROFILE,
    '.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright'));
(async () => {
    const data = JSON.parse(fs.readFileSync(process.env.QA_DATASET, 'utf8'));
    const browser = await chromium.launch({headless: true,
        executablePath: process.env.CHROME_EXECUTABLE || 'C:/Program Files/Google/Chrome/Application/chrome.exe'});
    try {
        const context = await browser.newContext({viewport: {width: 1440, height: 1050}, reducedMotion: 'reduce'});
        await context.addCookies([{name: process.env.QA_COOKIE_NAME, value: process.env.QA_SESSION, url: process.env.QA_URL}]);
        const page = await context.newPage(), errors = [];
        page.on('pageerror', error => errors.push(error.message));
        page.on('console', message => {if (message.type() === 'error') errors.push(message.text());});
        page.on('response', response => {if (response.status() >= 500) errors.push(response.url());});
        const go = async route => {
            const response = await page.goto(process.env.QA_URL + route, {waitUntil: 'networkidle'});
            assert.equal(response.status(), 200, route);
        };
        const shot = async name => {
            await page.evaluate(() => window.scrollTo(0, 0));
            await page.screenshot({path: path.join(process.env.QA_OUTPUT, name + '.png'), fullPage: true});
        };
        await go('/workspace/applications/');
        const nav = page.getByRole('navigation', {name: 'Administration navigation'});
        assert.equal(await page.locator('.workspace-module').count(), 8);
        assert.equal(await nav.getByRole('link', {name: 'Program Applications & Eligibility', exact: true}).count(), 1);
        assert.equal(await nav.getByRole('link', {name: /^(Non-EWAF Selection|EWAF Configuration|Eligibility Review|Program Applications)$/}).count(), 0);
        assert.equal(await nav.getByRole('link', {name:/^(Disability types|Registration settings|Eligibility statuses)$/i}).count(), 0);
        assert.equal(await page.locator('.program-card').count(), Math.min(20, Number(process.env.QA_PROGRAM_COUNT)));
        await page.locator('#program-search').fill('comparison');
        await page.locator('#program-type').selectOption('Healthcare & Medical Aid');
        await page.locator('#program-sort').selectOption('az');
        await page.locator('#program-applicants').check();
        await page.getByRole('button', {name: 'Apply filters', exact: true}).click();
        await page.waitForLoadState('networkidle');
        assert.equal(await page.locator('.program-card').count(), 1);
        assert.ok((await page.locator('.program-card').innerText()).includes('Medical support comparison'));
        await go('/workspace/applications/');
        await shot('program-applications');
        const program = data.demonstration_program, application = data.application_ids[program][0];
        const applicant = `/programs/manage/${program}/applications/${application}/`;
        await go(applicant);
        assert.equal(await page.locator('#eligibility form').count(), 1);
        assert.equal(await page.locator('#program-fit-review form').count(), 1);
        const ids = await page.locator('main [id]').evaluateAll(elements => elements.map(element => element.id));
        assert.equal(new Set(ids).size, ids.length, 'Application controls must have unique IDs for labels and keyboard focus');
        assert.ok((await page.locator('main').innerText()).includes('Income bracket'));
        await shot('applicant-eligibility');
        await go(`/ewaf/programs/${program}/`);
        for (const removed of ['Authority and selection policy', 'SI measurement and normalization',
            'ES measurement and normalization', 'PA measurement and normalization', 'ND measurement and normalization',
            'Program Relevance eligibility', 'Review confirmation']) {
            assert.equal(await page.getByText(removed, {exact: true}).count(), 0);
        }
        const expectedScores = JSON.parse(process.env.QA_CURRENT_SCORES);
        assert.equal(await page.locator('#results table tbody tr').count(), expectedScores.length);
        assert.ok((await page.locator('#results').innerText()).includes('Current verified calculation.'),
            await page.locator('#results').textContent());
        assert.ok(await page.locator('#results [name="decision-outcome"]').count() > 0);
        const scores = await page.locator('#results table tbody tr td:nth-child(3)').allTextContents();
        assert.deepEqual(scores.map(Number), expectedScores.map(score => Number(Number(score).toFixed(2))));
        const range = page.locator('#weight-SI');
        await range.focus(); await page.keyboard.press('ArrowRight');
        assert.equal(await page.locator('#weight-total').innerText(), '100.00%');
        const [preview] = await Promise.all([
            page.waitForResponse(response => response.request().method() === 'POST' && response.url() === page.url()),
            page.getByRole('button', {name: 'Review AHP result'}).click()
        ]);
        assert.equal(preview.status(), 200);
        assert.ok(preview.headers()['content-type'].includes('application/json'));
        assert.equal(await page.locator('#weight-preview-rows tr').count(), 4);
        await shot('ewaf-workspace');
        await page.locator('#results').screenshot({path: path.join(process.env.QA_OUTPUT, 'ewaf-results.png')});
        const routes = [applicant, `/ewaf/programs/${program}/`, '/workspace/applications/',
            `/assistance/releases/program/${data.receipt_program}/`, '/reports/applications/', '/membership/applications/new/',
            `/members/${process.env.QA_MEMBER}/`, '/events/manage/observances/',
            `/programs/manage/${program}/`, '/programs/manage/new/', `/membership/applications/${process.env.QA_REGISTRATION}/`];
        for (const route of routes) {
            await go(route);
            for (const width of [320, 390, 768, 1440]) {
                await page.setViewportSize({width, height: 1050});
                assert.equal(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth + 1), false, route + ' ' + width);
            }
            if (route.includes('/members/')) await shot('member-detail');
            if (route === '/membership/applications/new/') {
                assert.equal(await page.locator('[name=disability_types]').count(), 10);
                await shot('onsite-registration');
            } else if (route.includes('/membership/')) await shot('prpwd-review');
            if (route === '/programs/manage/new/') {
                assert.equal(await page.locator('[name=eligible_disability_types]').count(), 10);
                await shot('program-form');
            }
            if (route === `/programs/manage/${program}/`) await shot('program-overview');
            if (route.includes('/releases/')) await shot('assistance-releases');
            if (route.includes('/reports/')) await shot('application-report');
        }
        await page.setViewportSize({width: 390, height: 1050});
        await go(applicant); await shot('applicant-mobile');
        await go('/announcements/');
        await shot('announcements');
        for (const kind of ['members', 'applications', 'programs', 'assistance']) {
            const excel = await context.request.get(process.env.QA_URL + `/reports/${kind}/?format=xlsx`);
            assert.equal(excel.status(), 200);
            assert.ok(excel.headers()['content-type'].includes('spreadsheetml'));
            assert.ok((await excel.body()).subarray(0, 2).equals(Buffer.from('PK')));
        }
        assert.deepEqual(errors, []);
        console.log('PASS: live fictional portal; eight modules; exact ten shared choices; combined navigation; card filters; saved profiles; simplified eligibility; JSON AHP preview; actual scores; releases/reports; PRPWD controls; 44 responsive route-width checks; zero console/page/server errors.');
    } finally {await browser.close();}
})().catch(error => {console.error(error); process.exitCode = 1;});
