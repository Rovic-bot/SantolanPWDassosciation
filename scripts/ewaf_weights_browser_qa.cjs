const path = require('path');
const assert = require('assert/strict');
const {chromium} = require(process.env.PLAYWRIGHT_MODULE || path.join(process.env.USERPROFILE,
    '.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright'));
(async () => {
    const browser = await chromium.launch({headless: true,
        executablePath: process.env.CHROME_EXECUTABLE || 'C:/Program Files/Google/Chrome/Application/chrome.exe'});
    try {
        const context = await browser.newContext({viewport: {width: 1440, height: 1100}, reducedMotion: 'reduce'});
        await context.addCookies([{name: process.env.QA_COOKIE_NAME, value: process.env.QA_SESSION, url: process.env.QA_URL}]);
        const page = await context.newPage(), errors = [];
        page.on('pageerror', error => errors.push(error.message));
        await page.goto(`${process.env.QA_URL}/ewaf/programs/${process.env.QA_PROGRAM}/configuration/`, {waitUntil: 'networkidle'});
        const shot = async name => {
            // Start at the top so full-page captures place fixed navigation correctly.
            await page.evaluate(() => window.scrollTo(0, 0));
            await page.screenshot({path: path.join(process.env.QA_OUTPUT, name + '.png'), fullPage: true});
        };
        const read = () => page.locator('#weight-bars input').evaluateAll(inputs =>
            Object.fromEntries(inputs.map(input => [input.id.replace('weight-', ''), Number(input.value)])));
        const set = async (code, value) => {
            await page.locator('#weight-' + code).evaluate((input, value) => {
                input.value = String(value);
                input.dispatchEvent(new Event('input', {bubbles: true}));
                input.dispatchEvent(new Event('change', {bubbles: true}));
            }, value);
            assert.equal(await page.locator('#weight-total').textContent(), '100.00%');
        };
        const initial = await read();
        assert.equal(await page.locator('select[name^=pair_]').count(), 0);
        assert.equal(await page.locator('#weight-bars input[type=range]').count(), 4);
        assert.ok(await page.getByRole('button', {name: 'Lock configuration'}).isEnabled());
        await shot('saved-start');
        await page.locator('#weight-SI').scrollIntoViewIfNeeded();
        const slider = await page.locator('#weight-SI').boundingBox();
        await page.mouse.move(slider.x + slider.width * initial.SI / 10000, slider.y + slider.height / 2);
        await page.mouse.down();
        await page.mouse.move(slider.x + slider.width * .52, slider.y + slider.height / 2, {steps: 6});
        await page.mouse.up();
        const dragged = await read();
        assert.ok(dragged.SI > 5000 && dragged.SI < 5400);
        for (const code of ['ES', 'PA', 'ND']) {
            assert.ok(Math.abs(dragged[code] - initial[code] * (10000 - dragged.SI) / (10000 - initial.SI)) <= 1);
        }
        await page.getByRole('button', {name: 'Reset proposal'}).click();
        await set('SI', 5000);
        const first = await read();
        assert.equal(first.SI, 5000);
        for (const code of ['ES', 'PA', 'ND']) {
            assert.ok(Math.abs(first[code] - initial[code] * 5000 / (10000 - initial.SI)) <= 1);
        }
        await set('ES', 3000);
        const second = await read();
        assert.equal(second.SI, first.SI);
        assert.equal(second.ES, 3000);
        await set('PA', 1400);
        assert.deepEqual(await read(), {SI: 5000, ES: 3000, PA: 1400, ND: 600});
        await page.locator('#weight-PA').focus();
        await page.keyboard.press('End');
        assert.deepEqual(await read(), {SI: 5000, ES: 3000, PA: 1444, ND: 556});
        await page.getByRole('button', {name: 'Reset proposal'}).click();
        assert.deepEqual(await read(), initial);
        await set('SI', 5000); await set('ES', 3000); await set('PA', 1400);
        const move = page.getByRole('button', {name: 'Move Number of Dependents higher in priority'});
        await move.click(); await move.click();
        assert.deepEqual(await page.locator('.weight-row').evaluateAll(rows => rows.map(row => row.dataset.criterion)), ['SI', 'ND', 'ES', 'PA']);
        assert.deepEqual(await read(), {SI: 5000, ND: 3000, ES: 1400, PA: 600});
        const lock = page.getByRole('button', {name: 'Lock configuration'});
        assert.ok(await lock.isDisabled());
        const [response] = await Promise.all([
            page.waitForResponse(response => response.request().method() === 'POST' && response.url() === page.url().split('#')[0]),
            page.getByRole('button', {name: 'Review AHP result'}).click(),
        ]);
        assert.equal(response.status(), 200, await response.text());
        await page.locator('#weight-preview').waitFor({state: 'visible'});
        assert.equal(await page.locator('#weight-preview-rows tr').count(), 4);
        await page.locator('[name=accept_derived_weights]').check();
        assert.ok(await lock.isEnabled());
        // A previously accepted preview is invalidated by any weight change.
        await set('ES', 1399);
        assert.ok(await lock.isDisabled());
        assert.ok(await page.locator('#weight-preview').isHidden());
        await set('ES', 1400);
        await page.getByRole('button', {name: 'Review AHP result'}).click();
        await page.locator('#weight-preview').waitFor({state: 'visible'});
        await page.locator('[name=accept_derived_weights]').check();
        await shot('reviewed-proposal');
        for (const width of [320, 390, 768, 1440]) {
            await page.setViewportSize({width, height: 1100});
            assert.equal(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth + 1), false, 'overflow at ' + width);
            assert.ok(await page.locator('#weight-total').isVisible());
            const totalBox = await page.locator('#weight-total').boundingBox();
            assert.ok(totalBox.x >= 0 && totalBox.x + totalBox.width <= width, 'total outside viewport at ' + width);
        }
        await page.setViewportSize({width: 390, height: 1100});
        await shot('mobile-proposal');

        await page.locator('#configuration textarea[name=reason]').fill('Fictional explicit review of slider-derived AHP weights and priority order.');
        await page.locator('[name=attested]').check();
        await lock.click(); await page.waitForLoadState('networkidle');
        assert.ok((await page.locator('main').innerText()).includes('Version 2'));
        assert.deepEqual(await page.locator('.weight-row').evaluateAll(rows => rows.map(row => row.dataset.criterion)), ['SI', 'ND', 'ES', 'PA']);

        assert.ok((await page.locator('main').innerText()).includes('not independent pairwise judgments'));
        const savedWeights = await page.locator('[aria-label="Saved calculated AHP weights"] article').evaluateAll(rows =>
            Object.fromEntries(rows.map(row => [row.querySelector('h2').textContent, row.querySelector('p').textContent])));
        await page.goto(process.env.QA_URL + '/ewaf/', {waitUntil: 'networkidle'});
        const savedCard = page.locator(`.ewaf-program-card[data-program="${process.env.QA_PROGRAM}"]`);
        for (const [code, name] of Object.entries({SI:'Socioeconomic Indicator', ES:'Employment Status', PA:'Previous Assistance Received', ND:'Number of Dependents'})) {
            assert.equal(await savedCard.locator(`[data-criterion="${code}"] strong`).innerText(), savedWeights[name]);
        }
        assert.deepEqual(errors, []);
        console.log('Actual EWAF page passed: proportional cascades, fixed earlier weights, exact totals, keyboard bounds, reset, priority changes, preview invalidation, explicit AHP adoption, saved card weights refresh and 320/390/768/1440 layouts.');
    } finally { await browser.close(); }
})().catch(error => { console.error(error); process.exit(1); });
