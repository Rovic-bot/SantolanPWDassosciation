const path = require('path');
const assert = require('assert/strict');
const {chromium} = require(process.env.PLAYWRIGHT_MODULE || path.join(process.env.USERPROFILE,
    '.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright'));
(async () => {
    const browser = await chromium.launch({headless: true,
        executablePath: process.env.CHROME_EXECUTABLE || 'C:/Program Files/Google/Chrome/Application/chrome.exe'});
    try {
        const context = await browser.newContext({viewport: {width: 1440, height: 1000}, reducedMotion: 'reduce'});
        await context.addCookies([{name: process.env.QA_COOKIE_NAME, value: process.env.QA_SESSION, url: process.env.QA_URL}]);
        const page = await context.newPage(), errors = [];
        page.on('pageerror', error => errors.push(error.message));
        const shot = async name => {
            await page.evaluate(() => window.scrollTo(0, 0));
            await page.screenshot({path: path.join(process.env.QA_OUTPUT, name + '.png'), fullPage: true});
        };
        const responsive = async prefix => {
            for (const width of [1440, 768, 390, 320]) {
                await page.setViewportSize({width, height: 1000});
                const dimensions = await page.evaluate(() => ({
                    scroll: document.documentElement.scrollWidth, width: innerWidth}));
                assert.ok(dimensions.scroll <= dimensions.width + 1, `${prefix}: overflow at ${width}: ${JSON.stringify(dimensions)}`);
                if ([1440, 390].includes(width)) await shot(`${prefix}-${width}`);
            }
            await page.setViewportSize({width: 1440, height: 1000});
        };
        await page.goto(process.env.QA_URL + process.env.QA_PATH, {waitUntil: 'networkidle'});
        for (const title of ['Address Information', 'Personal Information', 'Disability Information',
            'Additional Information', 'Supporting Documents']) {
            assert.equal(await page.locator('legend').filter({hasText: new RegExp(`^${title}$`)}).count(), 1);
        }
        assert.equal(await page.locator('[name=disability_types]').count(), 10);
        assert.deepEqual(await page.locator('#id_disability_types label').allTextContents().then(labels => labels.map(label => label.trim())), ['Cancer (RA 11215)', 'Deaf or Hard of Hearing', 'Intellectual Disability', 'Learning Disability', 'Mental Disability', 'Physical Disability (Orthopedic)', 'Psychosocial Disability', 'Rare Disease (RA 10747)', 'Speech and Language Impairment', 'Visual Disability']);
        assert.deepEqual(await page.locator('#id_sex option').allTextContents(), ['---------', 'Male', 'Female']);
        for (const [name, value] of Object.entries({
            municipality: 'Pasig City', barangay: 'Santolan', house_number: '123',
            street: 'Sample Street', purok_zone: 'Zone 2', first_name: 'Mara', middle_name: 'Example',
            last_name: 'Santos', birthdate: '1990-06-12', contact_number: '09123456789',
            control_number: 'FICTIONAL-ONSITE-BROWSER', dependents: '2'})) {
            await page.locator(`#id_${name}`).fill(value);
        }
        await page.getByLabel('No Middle Name (N/A)', {exact: true}).check();
        assert.ok(await page.locator('#id_middle_name').isDisabled());
        await page.getByLabel('No Middle Name (N/A)', {exact: true}).uncheck();
        assert.ok(await page.locator('#id_middle_name').isEnabled());
        await page.getByLabel('No Middle Name (N/A)', {exact: true}).check();
        for (const [name, value] of Object.entries({suffix: 'other', sex: 'female', civil_status: 'single',
            disability_cause: 'acquired', disability_visibility: 'non_apparent', education: 'college',
            employment_status: 'self_employed', income_category: 'income_5000_10000'})) {
            await page.locator(`#id_${name}`).selectOption(value);
        }
        assert.ok(await page.locator('#id_suffix_other').isVisible());
        await page.locator('#id_suffix_other').fill('VII');
        await page.getByLabel('Cancer (RA 11215)', {exact: true}).check();
        await page.getByLabel('Deaf or Hard of Hearing', {exact: true}).check();
        for (const id of Object.keys(JSON.parse(process.env.QA_UPLOADS))) {
            await page.locator(`#id_document_${id}`).setInputFiles(process.env.QA_PHOTO);
        }
        await responsive('registration');
        await page.getByRole('button', {name: 'Save onsite registration for review'}).click();
        await page.waitForURL(/applications\/[a-f0-9-]+\/$/);
        await context.grantPermissions(['clipboard-read', 'clipboard-write']);
        await page.getByRole('button', {name:'Copy Control Number', exact:true}).click();
        assert.equal(await page.locator('#control-copy-status').innerText(), 'Control number copied.');
        assert.equal(await page.evaluate(() => navigator.clipboard.readText()), 'FICTIONAL-ONSITE-BROWSER');
        const prpwd = page.getByRole('link', {name:'Open PRPWD Verification', exact:true});
        assert.equal(await prpwd.getAttribute('href'), 'https://registry.example.test/');
        assert.equal(await prpwd.getAttribute('target'), '_blank');
        await context.route('https://registry.example.test/**', route => route.fulfill({
            contentType:'text/html', body:'<h1>Fictional external verification page</h1>'}));
        const [external] = await Promise.all([page.waitForEvent('popup'), prpwd.click()]);
        await external.waitForLoadState();
        assert.ok(external.url().startsWith('https://registry.example.test/'));
        await external.close();
        assert.ok((await page.locator('#prpwd-verification').innerText()).includes('Not yet checked'));
        const verify = page.locator('form').filter({has: page.locator('input[name=action][value=verify]')});
        await verify.locator('select').selectOption('yes');
        await verify.locator('textarea').fill('Fictional manual PRPWD verification for browser acceptance.');
        await verify.getByRole('button', {name: 'Save verification'}).click();
        await page.waitForLoadState('networkidle');
        const decide = page.locator('form').filter({has: page.locator('input[name=action][value=decide]')});
        await decide.locator('select').selectOption('approved');
        await decide.locator('textarea').fill('Fictional membership documents reviewed onsite.');
        await decide.getByRole('button', {name: 'Save membership decision'}).click();
        await page.getByRole('link', {name: /Open official member record/}).click();
        await page.waitForLoadState('networkidle');
        assert.equal(await page.getByRole('heading', {name: 'Mara Santos VII', exact: true}).count(), 1);
        assert.ok(await page.locator('.profile-portrait').evaluate(img => img.complete && img.naturalWidth > 0));
        await responsive('member-detail');
        const preview = page.getByRole('link', {name: 'Preview', exact: true}).first();
        const previewURL = await preview.getAttribute('href');
        const privateResponse = await context.request.get(process.env.QA_URL + previewURL);
        assert.equal(privateResponse.status(), 200);
        assert.ok(privateResponse.headers()['cache-control'].includes('no-store'));
        const anonymous = await browser.newContext();
        const blocked = await anonymous.request.get(process.env.QA_URL + previewURL, {maxRedirects: 0});
        assert.equal(blocked.status(), 302);
        await anonymous.close();
        await page.getByRole('link', {name: /Edit member profile/}).click();
        await page.locator('#id_dependents').fill('4');
        await page.locator('#id_employment_status').selectOption('retired');
        await page.locator('#id_notes').fill('Fictional verified source correction; reassessment required.');
        assert.equal(await page.locator('input[type=file]:disabled').count(), 5);
        await page.getByRole('button', {name: 'Save member changes'}).click();
        await page.waitForLoadState('networkidle');
        assert.ok((await page.locator('main').innerText()).includes('Retired'));
        await page.getByRole('link', {name: 'Verify for program reuse', exact: true}).first().click();
        await page.locator('#id_verified').selectOption('yes');
        await page.locator('#id_reason').fill('Fictional document checked against the onsite original.');
        await page.getByRole('button', {name: 'Record manual document review'}).click();
        await page.waitForLoadState('networkidle');
        assert.ok((await page.locator('main').innerText()).includes('Fictional document checked against the onsite original.'));
        assert.deepEqual(errors, []);
        console.log('PASS: actual onsite create, six uploads, manual approval, profile edit, private preview, document review, and 1440/768/390/320px layouts; zero page errors.');
    } finally { await browser.close(); }
})().catch(error => {console.error(error); process.exitCode = 1;});
