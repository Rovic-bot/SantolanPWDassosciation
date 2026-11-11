const fs = require('fs'), path = require('path'), assert = require('assert/strict');
const {chromium} = require(process.env.PLAYWRIGHT_MODULE || path.join(process.env.USERPROFILE,
    '.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright'));
const root = path.resolve(__dirname, '..'), local = path.join(root, '.local/main-testing');
const manifest = JSON.parse(fs.readFileSync(path.join(local, 'connection.json'), 'utf8'));
const data = JSON.parse(fs.readFileSync(path.join(path.dirname(manifest.media), 'dataset.json'), 'utf8'));
const login = JSON.parse(fs.readFileSync(path.join(local, 'login.json'), 'utf8'));
const output = path.join(local, 'screenshots'); fs.mkdirSync(output, {recursive: true});
const url = 'http://127.0.0.1:8000';
(async () => {
    const browser = await chromium.launch({headless: true, executablePath: process.env.CHROME_EXECUTABLE || 'C:/Program Files/Google/Chrome/Application/chrome.exe'});
    const results = {routes: [], responsive: [], downloads: [], actions: [], errors: []};
    try {
        const context = await browser.newContext({viewport: {width: 1440, height: 1000}, reducedMotion: 'reduce'});
        const page = await context.newPage(); page.setDefaultTimeout(120000);
        page.on('pageerror', error => results.errors.push(error.message));
        page.on('response', response => {if (response.status() >= 500) results.errors.push(response.url() + ':' + response.status());});
        const go = async route => {
            const started = Date.now();
            const response = await page.goto(url + route, {waitUntil: 'networkidle', timeout: 180000});
            assert.equal(response.status(), 200, route);
            assert.equal(response.headers()['x-santolan-environment'], 'MAIN-FICTIONAL-TESTING');
            results.routes.push({route, milliseconds: Date.now() - started});
        };
        const shot = async name => {await page.screenshot({path: path.join(output, name + '.png'), fullPage: false});};
        const post = async button => {
            await Promise.all([page.waitForNavigation({waitUntil:'networkidle', timeout:180000}), button.click()]);
            assert.ok(!(await page.locator('.errorlist').allTextContents()).some(text => text.trim()), await page.locator('.errorlist').allTextContents());
        };
        await go('/accounts/login/');
        await page.locator('[name=username]').fill(login.username);
        await page.locator('[name=password]').fill(login.password);
        await post(page.getByRole('button', {name:'Sign in', exact:true}));
        results.actions.push('Real Admin login with isolated cookies');
        if (process.argv.includes('--restored-only')) {
            await go('/testing/');
            await shot('01-testing-workspace');
            assert.ok((await page.locator('main').innerText()).includes('1800'));
            await page.setViewportSize({width:390,height:844});
            await shot('09-mobile-workspace');
            await page.setViewportSize({width:1440,height:1000});
            const balanced = data.programs['EWAF Lab — Balanced Weights'];
            await go(`/ewaf/programs/${balanced}/`);
            assert.ok((await page.locator('#results').innerText()).includes('Current verified calculation.'));
            assert.ok((await page.locator('#results table tbody tr').first().innerText()).includes('Elio'));
            await page.locator('#results').scrollIntoViewIfNeeded();
            await shot('11-restored-balanced-results');
            assert.deepEqual(results.errors, []);
            fs.writeFileSync(path.join(local,'restored-browser-results.json'),JSON.stringify(results,null,2));
            console.log('PASS: restored baseline login, live counts, balanced tied result and mobile workspace.');
            return;
        }
        if (process.argv.includes('--publication-only')) {
            const pending = data.programs['EWAF Lab — Pending Evidence'];
            const application = data.application_ids[pending][0];
            await go(`/programs/manage/${pending}/applications/${application}/`);
            const targets = await page.locator('a.review-check[data-review-target]').evaluateAll(links => links.map(link => link.dataset.reviewTarget));
            for (const target of targets) {
                await page.locator(`a.review-check[data-review-target="${target}"]`).first().click();
                assert.equal(await page.locator('#' + target).count(), 1);
                assert.ok(await page.locator('#' + target).isVisible());
            }
            const eligibility = page.locator('#eligibility-decision-form');
            await eligibility.locator('textarea').fill('Fictional browser review: supporting evidence remains incomplete; request correction.');
            const [review] = await Promise.all([
                page.waitForResponse(response => response.request().method() === 'POST'),
                eligibility.getByRole('button', {name:'Needs Information', exact:true}).click()
            ]);
            assert.equal(review.status(), 302);
            await page.waitForLoadState('networkidle');
            assert.ok((await page.locator('main').innerText()).includes('Needs Information'));
            results.actions.push('Click-to-review targets and saved Needs Information decision');
            const program = data.programs['Community Pantry — Historical Round 3'];
            await go(`/announcements/manage/recipients/${program}/`);
            await page.locator('[name=reason]').fill('Fictional browser test: only confirmed non-voided receipts, reviewed masked projection.');
            await page.locator('[name=confirm]').check();
            await post(page.getByRole('button', {name:'Prepare public preview',exact:true}));
            const publication = page.locator('aside form');
            await publication.locator('[name=action]').selectOption('published');
            await publication.locator('[name=confirm]').check();
            await post(publication.getByRole('button', {name:'Apply publication change',exact:true}));
            await page.getByRole('link', {name:/View public announcement/}).click();
            await page.waitForLoadState('networkidle');
            await shot('10-recipient-publication');
            results.actions.push('Recipient preview, explicit publication and public masked view');
            await go('/members/');
            const first = await page.locator('table tbody tr').allTextContents();
            await go('/members/?page=2');
            const second = await page.locator('table tbody tr').allTextContents();
            assert.ok(first.length && second.length && !first.some(row => second.includes(row)));
            results.actions.push('Member pagination has distinct records');
            assert.deepEqual(results.errors, []);
            fs.writeFileSync(path.join(local,'publication-browser-results.json'),JSON.stringify(results,null,2));
            console.log('PASS: review links, eligibility correction, recipient publication, and distinct member pages.');
            return;
        }
        await go('/testing/'); await shot('01-testing-workspace');
        await go('/workspace/applications/'); await shot('02-program-applications');
        await page.locator('#program-search').fill('EWAF Lab');
        await post(page.getByRole('button', {name:'Apply filters', exact:true}));
        assert.ok(await page.locator('.program-card').count() >= 8);
        const balanced = data.programs['EWAF Lab — Balanced Weights'];
        const selected = data.programs['EWAF Lab — Selection & Slots'];
        const release = data.programs['EWAF Lab — Assistance Release'];
        await go(`/ewaf/programs/${balanced}/`);
        assert.ok((await page.locator('#results').innerText()).includes('Current verified calculation.'));
        results.before = await page.locator('#results table tbody tr').allTextContents();
        await page.getByRole('button', {name:'Move Employment Status higher in priority', exact:true}).click();
        await page.locator('#weight-ES').evaluate(input => {input.value='7000'; input.dispatchEvent(new Event('input', {bubbles:true}));});
        assert.equal(await page.locator('#weight-total').innerText(), '100.00%');
        await page.getByRole('button', {name:'Review AHP result', exact:true}).click();
        await page.locator('#weight-preview').waitFor({state:'visible'});
        assert.equal(await page.locator('#weight-preview-rows tr').count(), 4);
        await page.locator('[name=accept_derived_weights]').check();
        const form = page.locator('#ewaf-configuration-form');
        await form.locator('[name=reason]').fill('Fictional browser test: employment emphasis with reviewed AHP weights.');
        await form.locator('[name=attested]').check();
        await shot('03-weight-experiment');
        await post(page.getByRole('button', {name:'Lock configuration', exact:true}));
        assert.ok((await page.locator('#results').innerText()).includes('Information has changed.'));
        const generate = page.locator('#calculate form');
        await generate.locator('[name=reason]').fill('Fictional browser test: recalculate all verified applicants.');
        await post(page.getByRole('button', {name:'Generate EWAF', exact:true}));
        results.after = await page.locator('#results table tbody tr').allTextContents();
        assert.notEqual(results.before[0], results.after[0]);
        await page.locator('#results').scrollIntoViewIfNeeded(); await shot('04-ewaf-results');
        results.actions.push('Reorder criteria, cascade to 100%, preview AHP, lock revision, stale rejection, regenerate, changed leading applicant');
        await go(`/ewaf/programs/${selected}/`);
        const decision = page.locator('#results table tbody tr').first();
        await decision.locator('summary').click();
        const application = await decision.locator('[name="decision-application_id"]').inputValue();
        await decision.locator('[name="decision-outcome"]').selectOption('SELECTED');
        await decision.locator('[name="decision-reason"]').fill('Fictional browser test: human choice within remaining slots.');
        await decision.locator('[name="decision-tie_reason"]').fill('Fictional human review of need and capacity; scores remain unchanged.');
        await post(decision.getByRole('button', {name:'Save beneficiary decision', exact:true}));
        results.actions.push('Human beneficiary selection with reason');
        await go(`/assistance/${application}/release/`);
        await page.locator('[name=assistance_type]').fill('Food & Nutrition');
        await page.locator('[name=benefit]').fill('Fictional food support package');
        await page.locator('[name=released_on]').fill(new Intl.DateTimeFormat('en-CA', {timeZone:'Asia/Manila',year:'numeric',month:'2-digit',day:'2-digit'}).format(new Date()));
        await page.locator('[name=reference]').fill('LAB-BROWSER-RECEIPT');
        await page.locator('[name=notes]').fill('Fictional browser test: package handed over and receipt confirmed.');
        await page.locator('[name=confirm]').check();
        await post(page.locator('main form button[type=submit]'));
        assert.ok((await page.locator('main').innerText()).includes('LAB-BROWSER-RECEIPT'));
        results.actions.push('Confirmed assistance receipt from actual selected application');
        await go(`/assistance/releases/program/${release}/`); await shot('05-assistance-releases');
        const applicant = data.application_ids[balanced][0];
        const routes = ['/testing/', '/workspace/applications/', '/members/', '/programs/manage/new/',
            '/membership/applications/new/', `/programs/manage/${balanced}/applications/${applicant}/`,
            `/ewaf/programs/${balanced}/`, `/assistance/releases/program/${release}/`,
            '/reports/applications/', '/events/manage/observances/', '/announcements/manage/'];
        for (const route of routes) {
            await go(route);
            for (const width of [320,390,768,1440]) {
                await page.setViewportSize({width,height:1000});
                assert.equal(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth + 1), false, route + ' width ' + width);
                results.responsive.push({route,width});
            }
            if (route.includes('/applications/') && route.includes(balanced)) await shot('06-applicant-review');
            if (route.includes('/reports/')) await shot('07-application-report');
            if (route.includes('/observances/')) await shot('08-annual-observances');
        }
        await page.setViewportSize({width:390,height:844}); await go('/testing/'); await shot('09-mobile-workspace');
        for (const kind of ['members','programs','applications','assistance']) {
            for (const format of ['csv','xlsx','pdf']) {
                const response = await context.request.get(url + `/reports/${kind}/?format=${format}`, {timeout:180000});
                assert.equal(response.status(),200);
                const bytes = await response.body(); assert.ok(bytes.length > 10);
                if (format === 'pdf') assert.ok(bytes.subarray(0,5).equals(Buffer.from('%PDF-')));
                if (format === 'xlsx') assert.ok(bytes.subarray(0,2).equals(Buffer.from('PK')));
                results.downloads.push({kind,format,bytes:bytes.length});
            }
        }
        assert.deepEqual(results.errors, []);
        fs.writeFileSync(path.join(local,'browser-results.json'),JSON.stringify(results,null,2));
        console.log('PASS:', results.actions.length, 'interactive workflows;', results.responsive.length, 'responsive checks;', results.downloads.length, 'exports; no page/server errors.');
    } finally {await browser.close();}
})().catch(error => {console.error(error); process.exitCode=1;});
