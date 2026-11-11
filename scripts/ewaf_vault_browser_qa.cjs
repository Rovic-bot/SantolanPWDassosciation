const path = require('path');
const assert = require('assert/strict');
const {chromium} = require(process.env.PLAYWRIGHT_MODULE || path.join(process.env.USERPROFILE,
    '.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright'));

(async () => {
    const browser = await chromium.launch({headless: true,
        executablePath: process.env.CHROME_EXECUTABLE || 'C:/Program Files/Google/Chrome/Application/chrome.exe'});
    try {
        const context = await browser.newContext({viewport: {width: 1365, height: 1000}, reducedMotion: 'reduce'});
        await context.addCookies([{name: process.env.QA_COOKIE_NAME, value: process.env.QA_SESSION, url: process.env.QA_URL}]);
        const page = await context.newPage(), errors = [];
        page.on('pageerror', error => errors.push(error.message));
        await page.goto(`${process.env.QA_URL}/ewaf/vault/`, {waitUntil: 'networkidle'});
        const approve = page.getByRole('button', {name: 'Approve configuration', exact: true});
        assert.equal(await page.locator('#weight-bars input[type=range]').count(), 5);
        assert.equal(await page.locator('form input[type=checkbox], form textarea, form select').count(), 0);
        assert.equal(await approve.isEnabled(), true);
        await page.screenshot({path: path.join(process.env.QA_OUTPUT, 'configuration-desktop.png'), fullPage: true});
        await approve.click();
        await page.getByRole('heading', {name: 'Approved version 1', exact: true}).waitFor();
        await page.locator('#weight-HI').evaluate(input => {
            input.value = '4000';
            input.dispatchEvent(new Event('input', {bubbles: true}));
        });
        assert.equal(await approve.isEnabled(), true);
        assert.equal(await page.locator('#weight-total').innerText(), '100.00%');
        await approve.click();
        await page.getByRole('heading', {name: 'Approved version 2', exact: true}).waitFor();
        await page.setViewportSize({width: 390, height: 844});
        assert(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth));
        await page.screenshot({path: path.join(process.env.QA_OUTPUT, 'configuration-mobile.png'), fullPage: true});
        assert.deepEqual(errors, []);
        console.log('One-click approval, changed weights, removed fields, mobile layout and JavaScript checks passed.');
    } finally {
        await browser.close();
    }
})().catch(error => { console.error(error); process.exit(1); });
