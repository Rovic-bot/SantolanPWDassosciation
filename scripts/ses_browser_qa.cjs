'use strict';
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const {chromium} = require(process.env.PLAYWRIGHT_MODULE || path.join(process.env.USERPROFILE,
    '.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright'));
const {valid} = require('../static/js/ewaf-weights.js');

(async () => {
    const artifact = process.env.G12_ARTIFACT_DIR;
    assert.ok(artifact && path.basename(artifact).startsWith('santolan-g12-tests-'), 'Disposable harness required');
    const browser = await chromium.launch({headless: true,
        executablePath: process.env.CHROME_EXECUTABLE || 'C:/Program Files/Google/Chrome/Application/chrome.exe'});
    const output = path.join(artifact, 'ses-browser');
    fs.mkdirSync(output, {recursive: true});
    try {
        const context = await browser.newContext({viewport: {width: 1280, height: 960}});
        await context.addCookies([{name: 'sessionid', value: process.env.SES_QA_SESSION, url: process.env.SES_QA_URL}]);
        const page = await context.newPage(), errors = [];
        page.on('pageerror', error => errors.push(error.message));
        const go = async key => {
            const response = await page.goto(process.env.SES_QA_URL + process.env[key], {waitUntil: 'networkidle'});
            assert.equal(response.status(), 200, key);
        };
        const read = () => page.locator('[name="slider_proposal"]').inputValue().then(JSON.parse);
        const ready = () => page.locator('#weight-preview:not([hidden])').waitFor();
        const layout = async name => {
            for (const width of [390, 768, 1280]) {
                await page.setViewportSize({width, height: 960});
                assert.equal(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth + 1), false,
                    `${name}: horizontal overflow at ${width}`);
            }
            await page.screenshot({path: path.join(output, name + '.png'), fullPage: true});
        };
        await go('SES_QA_VAULT');
        await ready();
        assert.equal(await page.locator('#weight-bars input[type="range"]').count(), 4);
        assert.equal(await page.locator('#weight-HI, #weight-SI').count(), 0);
        assert.equal(await page.locator('#weight-HM').isDisabled(), true);
        for (const code of ['SES', 'ES', 'PA', 'HM']) {
            const slider = page.locator('#weight-' + code);
            assert.equal(await slider.getAttribute('min'), '0');
            assert.equal(await slider.getAttribute('max'), '100');
            assert.equal(await slider.getAttribute('step'), '0.01');
        }
        assert.match(await page.locator('#weight-consistency').innerText(), /PASSED.*RI 0.90.*4 criteria/);
        assert.match(await page.locator('#weight-origin').innerText(), /version/i);
        const before = await read();
        await page.locator('#weight-ES').focus();
        await page.keyboard.press('ArrowRight');
        let changed = await read();
        assert.equal(changed.weights.SES, before.weights.SES);
        assert.equal(changed.weights.ES, before.weights.ES + 1);
        assert.equal(changed.weights.PA + changed.weights.HM, before.weights.PA + before.weights.HM - 1);
        assert.ok(valid(changed));
        for (let move = 0; move < 3; move++) {
            const up = page.locator('[data-criterion="HM"] button').first();
            await up.focus(); await page.keyboard.press('Enter');
        }
        assert.equal((await read()).order[0], 'HM');
        assert.equal(await page.locator('#weight-HM').isDisabled(), false);
        assert.equal(await page.locator('#weight-PA').isDisabled(), true);
        await page.locator('#weight-HM').focus();
        await page.keyboard.press('End');
        assert.ok(valid(await read()));
        assert.ok((await read()).weights.HM < 10000);
        await page.keyboard.press('Home');
        assert.ok(valid(await read()));
        assert.ok((await read()).weights.HM > 0);
        await page.locator('#reset-weights').click(); await ready();
        assert.deepEqual(await read(), before);
        assert.equal(await page.locator('button[name="action"][value="LOCKED"]').isDisabled(), true);
        await page.locator('#id_reason').fill('SYNTHETIC browser saved draft review');
        await page.locator('button[name="action"][value="DRAFT"]').click();
        await page.waitForLoadState('networkidle'); await ready();
        assert.equal(await page.locator('button[name="action"][value="LOCKED"]').isDisabled(), false);
        await layout('ses-vault-draft');
        await page.locator('#id_reason').fill('SYNTHETIC browser approval in disposable database only');
        await page.locator('button[name="action"][value="LOCKED"]').click();
        await page.waitForLoadState('networkidle'); await ready();
        assert.deepEqual(await read(), before);
        await go('SES_QA_OLD_VAULT'); await ready();
        assert.equal(await page.locator('#weight-bars input[type="range"]').count(), 5);
        assert.equal(await page.locator('#weight-HI, #weight-SI').count(), 2);
        assert.equal(await page.locator('#weight-SES').count(), 0);
        await layout('historical-five-vault');
        await go('SES_QA_POLICY');
        assert.equal(await page.locator('[name="si_rubric"], [name="evidence_SI"]').count(), 0);
        assert.equal(await page.locator('[name="ses_measure"]').count(), 1);
        await layout('ses-policy');
        await go('SES_QA_INPUTS');
        assert.equal(await page.locator('[name="si_four_ps"], [name="si_indigency"]').count(), 0);
        assert.equal(await page.locator('[name="income_consistency"]').count(), 1);
        assert.equal(await page.locator('[name^="evidence_"]').count(), 4);
        await layout('ses-inputs');
        await go('SES_QA_BREAKDOWN'); await layout('ses-breakdown');
        assert.deepEqual(errors, []);
        console.log('PASS: SES sliders, keyboard, priority arrows, draft/approval, policy, accepted inputs, breakdown; historical five-criterion controls.');
    } finally { await browser.close(); }
})().catch(error => { console.error(error); process.exitCode = 1; });
