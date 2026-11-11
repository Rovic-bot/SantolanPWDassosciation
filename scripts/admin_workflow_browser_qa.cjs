const path = require('path');
const fs = require('fs');
const assert = require('assert/strict');
const runtime = path.join(process.env.USERPROFILE, '.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
const {chromium} = require(process.env.PLAYWRIGHT_MODULE || runtime);
(async () => {
    const browser = await chromium.launch({headless: true,
        executablePath: process.env.CHROME_EXECUTABLE || 'C:/Program Files/Google/Chrome/Application/chrome.exe'});
    try {
        const context = await browser.newContext({viewport: {width: 1440, height: 1100}, reducedMotion: 'reduce'});
        await context.addCookies([{name: process.env.QA_COOKIE_NAME, value: process.env.QA_SESSION, url: process.env.QA_URL}]);
        const page = await context.newPage();
        const errors = [];
        page.on('pageerror', error => errors.push(error.message));
        page.on('response', response => { if (response.status() >= 500) errors.push(`${response.status()} ${response.url()}`); });
        const go = async route => {
            const response = await page.goto(process.env.QA_URL + route, {waitUntil: 'networkidle'});
            assert.equal(response.status(), 200, route);
        };
        const shot = async name => page.screenshot({path: path.join(process.env.QA_OUTPUT, name + '.png'), fullPage: true});
        const click = async locator => { await locator.click(); await page.waitForLoadState('networkidle'); };
        await go('/admin/documents/documenttype/');
        const documentSidebar = page.getByRole('navigation', {name: 'Administration navigation'});
        assert.equal(await documentSidebar.getByRole('link', {name: 'Documents', exact: true}).count(), 1);
        assert.equal(await documentSidebar.getByRole('link', {name: /^Document (types|requirements)$/}).count(), 0);
        const documentTabs = page.getByRole('navigation', {name: 'Document configuration', exact: true});
        assert.equal(await documentTabs.locator('[aria-current=page]').innerText(), 'Document types');
        await click(documentTabs.getByRole('link', {name: 'Document requirements'}));
        assert.ok(new URL(page.url()).pathname.endsWith('/documents/membershipdocumentrequirement/'));
        assert.equal(await documentSidebar.locator('a[aria-current=page]').innerText(), 'Documents');
        assert.equal(await documentTabs.locator('[aria-current=page]').innerText(), 'Document requirements');
        await shot('document-navigation');
        for (const width of [320, 390, 768, 1440]) {
            await page.setViewportSize({width, height: 1100});
            assert.equal(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth + 1), false, 'document navigation overflow at ' + width);
            assert.ok(await documentTabs.getByRole('link', {name: 'Document types'}).isVisible());
            assert.ok(await documentTabs.getByRole('link', {name: 'Document requirements'}).isVisible());
        }
        await click(documentTabs.getByRole('link', {name: 'Document types'}));
        assert.equal(await documentSidebar.locator('a[aria-current=page]').innerText(), 'Documents');
        await go('/programs/manage/new/');
        const navigation = await page.getByRole('navigation', {name: 'Administration navigation'}).innerText();
        for (const label of ['Create program', 'Create event', 'Photo Verification Queue', 'Criterion evidence', 'Scoring-policy diagnostics', 'Historical EWAF information', 'Prepare program results']) {
            assert.ok(!navigation.includes(label), label);
        }
        assert.equal(await page.locator('[name=amount], [name=benefit]').count(), 0);
        assert.equal(await page.locator('[name=assistance_type] option').count(), 3);
        assert.equal(await page.locator('[name=eligible_disability_types]').count(), 10);
        assert.deepEqual(await page.locator('#id_eligible_disability_types label').allTextContents().then(labels => labels.map(label => label.trim())), ['Cancer (RA 11215)', 'Deaf or Hard of Hearing', 'Intellectual Disability', 'Learning Disability', 'Mental Disability', 'Physical Disability (Orthopedic)', 'Psychosocial Disability', 'Rare Disease (RA 10747)', 'Speech and Language Impairment', 'Visual Disability']);
        await page.locator('[name=name]').fill('Fictional browser proposal');
        await page.locator('textarea[name=description]').fill('A synthetic assistance program used only for isolated browser testing.');
        await page.locator('[name=assistance_type]').selectOption('Assistive Devices');
        await page.locator('[name=registration_opens_at]').fill('2027-02-01T09:00');
        await page.locator('[name=registration_closes_at]').fill('2027-02-15T17:00');
        await page.locator('[name=starts_at]').fill('2027-03-01T09:00');
        await page.locator('[name=ends_at]').fill('2027-03-01T17:00');
        await page.locator('[name=slots]').fill('2');
        await page.locator('[name=requirements]').fill('Fictional instructions for this draft.');
        await page.locator('[name=selection_method]').fill('Fictional documented human selection.');
        await page.locator('[name=photo_instructions]').fill('Fictional manual photo review instructions.');
        await page.getByRole('button', {name: 'Add requirement', exact:true}).click();
        await page.locator('[name="requirements-0-label"]').fill('Fictional supporting document');
        await page.locator('[name="requirements-0-kind"]').selectOption('document');
        await page.getByRole('button', {name: 'Add requirement'}).click();
        await page.locator('[name="requirements-1-label"]').fill('Fictional acknowledgement');
        await page.locator('[name="requirements-1-kind"]').selectOption('acknowledgement');
        await shot('program-form');
        await click(page.getByRole('button', {name: 'Create program', exact: true}));
        assert.ok(/\/programs\/manage\/[a-f0-9-]+\/$/.test(new URL(page.url()).pathname), await page.locator('main').innerText());
        const createdProgramUrl = new URL(page.url()).pathname;
        await shot('program-details');
        const proposal = page.getByRole('link', {name:'Download Proposal PDF', exact:true});
        const pdf = await context.request.get(process.env.QA_URL + await proposal.getAttribute('href'));
        assert.equal(pdf.status(), 200);
        const pdfPath = path.join(process.env.QA_OUTPUT, 'program-proposal.pdf');
        fs.writeFileSync(pdfPath, await pdf.body());
        assert.ok(fs.readFileSync(pdfPath).subarray(0, 5).equals(Buffer.from('%PDF-')));
        await click(page.getByRole('link', {name: 'Edit Program', exact: true}));
        assert.equal(await page.locator('[name=requirements]').inputValue(), 'Fictional instructions for this draft.');
        await page.locator('[name=notes]').fill('Fictional draft correction.');
        await page.locator('textarea[name=description]').fill('Updated synthetic proposal for isolated testing.');
        await click(page.getByRole('button', {name: 'Save changes', exact: true}));
        await go('/workspace/applications/');
        assert.ok(await page.locator('.program-grid .program-card').count() >= 3);
        assert.ok((await page.locator('main').innerText()).includes('Created'));
        await shot('application-programs');
        const appUrl = `/programs/manage/${process.env.QA_REVIEW_PROGRAM}/applications/${process.env.QA_REVIEW_APPLICATION}/`;
        await go(appUrl);
        assert.equal(await page.locator('.profile-avatar').count(), 1);
        assert.ok(await page.locator('.profile-avatar').evaluate(img => img.complete && img.naturalWidth > 0));
        const documentLink = page.getByRole('link', {name: 'Preview', exact: true});
        assert.equal(await documentLink.count(), 1);
        const privateDocument = await context.request.get(process.env.QA_URL + await documentLink.getAttribute('href'));
        assert.equal(privateDocument.status(), 200);
        assert.ok(privateDocument.headers()['content-type'].includes('application/pdf'));
        await page.locator('[data-check="photo"]').click();
        await page.locator('form').filter({has: page.locator('[name=action][value=photo]')}).locator('[name=reason]').fill('Fictional browser manual verification of the supplied photo.');
        await page.locator('form').filter({has: page.locator('[name=action][value=photo]')}).locator('[name=confirm]').check();
        await click(page.getByRole('button', {name: 'Verify Identity', exact:true}));
        await page.waitForFunction(() => !document.querySelector('form[data-saving]'));
        await shot('applicant-review');
        assert.equal(await page.locator('.profile-header').count(), 1);
        await page.locator('[data-check="documents"]').click();
        for (const check of await page.locator('input[name^=check_][value=pass]').all()) await check.check();
        await page.locator('[name=other_requirements][value=pass]').check();
        await page.locator('#eligibility [name=notes]').fill('Verified membership, photo and original program requirements in this fictional review.');
        await shot('eligibility-review');
        await click(page.getByRole('button', {name: 'Mark Eligible', exact: true}));
        await page.waitForFunction(() => !document.querySelector('form[data-saving]'));
        assert.ok((await page.locator('main').innerText()).includes('Eligible'));
        for (const [id, check, action, outcome] of [
            [process.env.QA_NEGATIVE_APPLICATION, 'fail', 'Mark Ineligible', 'Ineligible'],
            [process.env.QA_PENDING_APPLICATION, 'review', 'Needs Information', 'Needs Information']]) {
            await go(`/programs/manage/${process.env.QA_REVIEW_PROGRAM}/applications/${id}/`);
            await page.locator('[data-check="documents"]').click();
            await page.locator(`[name=other_requirements][value=${check}]`).check();
            await page.locator('#eligibility [name=notes]').fill(check === 'fail' ?
                'Fictional officer confirms a mandatory program condition is not met; this is not a missing-document decision.' :
                'Fictional correctable information needs further verification.');
            await click(page.getByRole('button', {name:action, exact:true}));
            await page.waitForFunction(() => !document.querySelector('form[data-saving]'));
            assert.ok((await page.locator('#eligibility [role=status]').innerText()).includes(outcome));
        }
        // Configure, calculate and choose using the actual Admin forms.
        await go(`/ewaf/programs/${process.env.QA_PROGRAM}/configuration/`);
        assert.equal(await page.locator('select[name^="pair_"]').count(), 0);
        assert.equal(await page.locator('#weight-bars input[type=range]').count(), 4);

        await page.locator('#configuration textarea[name=reason]').fill('Fictional approval for isolated browser calculation.');
        await page.locator('#configuration [name=attested]').check();
        await click(page.getByRole('button', {name: 'Lock configuration'}));
        assert.ok((await page.locator('main').innerText()).includes('Authorized and locked'));
        assert.equal(await page.getByText('AHP matrix and consistency calculation', {exact: true}).count(), 0);
        await shot('ewaf-configuration');
        await go(`/ewaf/programs/${process.env.QA_PROGRAM}/`);
        await page.locator('#calculate textarea[name=reason]').fill('Fictional complete-pool browser calculation.');
        await click(page.getByRole('button', {name: 'Generate EWAF', exact: true}));
        assert.ok((await page.locator('main').innerText()).includes('Current verified calculation'), await page.locator('main').innerText());
        assert.equal(await page.locator('#results table tbody tr').count(), 2);
        const resultUrl = new URL(page.url()).pathname;
        await shot('ewaf-ranked-results');
        const form = page.locator('form').filter({has: page.locator(`[name="decision-application_id"][value="${process.env.QA_APPLICATION}"]`)});
        await form.locator('..').locator('summary').click();
        await form.locator('[name="decision-outcome"]').selectOption('SELECTED');
        await form.locator('[name="decision-reason"]').fill('Fictional human selection following the approved policy and available slot.');
        await form.locator('[name="decision-tie_reason"]').fill('Fictional application of the documented tie procedure.');
        await click(form.getByRole('button', {name: 'Save beneficiary decision'}));
        await click(page.getByRole('link', {name: 'Assistance releases', exact: true}).last());
        assert.ok((await page.locator('main').innerText()).includes('Not recorded'));
        await shot('assistance-selections');
        await click(page.getByRole('link', {name: 'Record actual receipt'}));
        await page.locator('[name=assistance_type]').fill('Assistive Devices');
        await page.locator('[name=benefit]').fill('Fictional delivered assistance');
        const today = new Intl.DateTimeFormat('en-CA', {timeZone: 'Asia/Manila', year: 'numeric', month: '2-digit', day: '2-digit'}).format(new Date());
        await page.locator('[name=released_on]').fill(today);
        await page.locator('[name=notes]').fill('Fictional assistance receipt confirmed in the browser.');
        await page.locator('[name=confirm]').check();
        await click(page.getByRole('button', {name: 'Confirm assistance release'}));
        assert.ok((await page.locator('main').innerText()).includes('Fictional delivered assistance'), await page.locator('main').innerText());
        await go(`/assistance/releases/program/${process.env.QA_PROGRAM}/`);
        await shot('assistance-receipts');
        await go('/announcements/manage/');
        assert.equal(await page.getByText('How to use announcements', {exact: true}).count(), 0);
        await click(page.getByRole('link', {name: 'Publish assistance recipients'}));
        await page.locator('[name=program]').selectOption(process.env.QA_PROGRAM);
        await click(page.getByRole('button', {name: 'Continue to program'}));
        await page.locator('[name=reason]').fill('Fictional confirmed recipient announcement for isolated browser verification.');
        await page.locator('[name=confirm]').check();
        await click(page.getByRole('button', {name: 'Prepare public preview'}));
        assert.ok((await page.locator('main').innerText()).includes('Received'));
        await shot('recipient-preview');
        await page.locator('[name=action]').selectOption('published');
        await page.locator('[name=confirm]').check();
        await click(page.getByRole('button', {name: 'Apply publication change'}));
        await click(page.getByRole('link', {name: /^View public announcement/}));
        assert.ok((await page.locator('main').innerText()).includes('Confirmed assistance recipients'));
        assert.ok(!(await page.locator('main').innerText()).includes(process.env.QA_MEMBER_NAME));
        await shot('public-recipients');
        for (const kind of ['members', 'applications', 'programs', 'assistance']) {
            await go(`/reports/${kind}/`);
            const csv = await context.request.get(process.env.QA_URL + `/reports/${kind}/?format=csv`);
            assert.equal(csv.status(), 200);
            assert.ok(csv.headers()['content-type'].includes('text/csv'));
            const pdf = await context.request.get(process.env.QA_URL + `/reports/${kind}/?format=pdf`);
            assert.equal(pdf.status(), 200);
            assert.ok((await pdf.body()).subarray(0, 5).equals(Buffer.from('%PDF-')));
            fs.writeFileSync(path.join(process.env.QA_OUTPUT, kind + '-report.pdf'), await pdf.body());
        }
        await shot('assistance-report');
        for (const route of [createdProgramUrl, '/workspace/applications/', appUrl,
            `/ewaf/programs/${process.env.QA_PROGRAM}/configuration/`, resultUrl,
            `/assistance/releases/program/${process.env.QA_PROGRAM}/`, '/reports/programs/', '/events/manage/observances/']) {
            await go(route);
            for (const width of [320, 390, 768, 1440]) {
                await page.setViewportSize({width, height: 1000});
                assert.equal(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth + 1), false, `${route} at ${width}`);
            }
            assert.equal(await page.locator('main h1').count(), 1, route);
        }
        await go('/events/');
        assert.equal(await page.locator('.observance-month').count(), 12);
        assert.equal(await page.getByRole('heading', {name: 'Association activities', exact: true}).count(), 0);
        await page.setViewportSize({width: 390, height: 1000});
        await go(appUrl);
        await shot('applicant-mobile');
        assert.deepEqual(errors, []);
        console.log('Admin browser passed: program create/edit and inline requirements; proposal PDF download; program grids; private photo review; eligibility; four-criterion configuration/calculation/selection; actual release; masked recipient publication; four CSV/PDF reports; annual observances; 320/390/768/1440 layouts.');
    } finally { await browser.close(); }
})().catch(error => { console.error(error); process.exit(1); });
