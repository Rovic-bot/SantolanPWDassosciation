/* Read-only checks; edge cases replace responses in this browser only. */
const { chromium } = require(process.env.PLAYWRIGHT_MODULE || 'C:/Users/rovic/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const origin = process.env.QA_URL || 'http://127.0.0.1:8013';
const output = 'docs/public-event-refined-2026-11-09';
(async () => {
    const browser = await chromium.launch({ headless: true, executablePath: process.env.CHROME_EXECUTABLE || 'C:/Program Files/Google/Chrome/Application/chrome.exe' });
    try {
        fs.mkdirSync(output, { recursive: true });
        const page = await browser.newPage(), errors = [], checks = [];
        page.on('pageerror', error => errors.push(error.message));
        const dialog = page.locator('[data-public-dialog]');
        const open = async () => {
            await page.locator('[data-event-popup]').first().click();
            await page.waitForSelector('.event-poster-dialog .event-poster-card');
        };
        for (const theme of ['light', 'dark']) {
            for (const width of [1440, 768, 390, 320]) {
                await page.setViewportSize({ width, height: 900 });
                await page.goto(origin + '/events/');
                await page.evaluate(theme => document.documentElement.dataset.publicTheme = theme, theme);
                await open();
                assert.equal(page.url(), origin + '/events/');
                const geometry = await dialog.evaluate(el => {
                    const rect = el.getBoundingClientRect();
                    return { width: rect.width, height: rect.height, overflow: el.scrollWidth - el.clientWidth, fits: rect.left >= 0 && rect.right <= innerWidth && rect.top >= 0 && rect.bottom <= innerHeight };
                });
                assert(geometry.fits && geometry.overflow <= 1);
                assert(geometry.width <= 800);
                assert.equal(await dialog.evaluate(el => getComputedStyle(el).backgroundColor), 'rgb(21, 33, 26)');
                assert.equal(await dialog.locator('.event-poster-badge').evaluate(el => getComputedStyle(el).color), 'rgb(37, 53, 47)');
                assert.equal(await dialog.locator('.event-poster-location').evaluate(el => getComputedStyle(el).color), 'rgb(162, 178, 196)');
                assert.equal(await dialog.locator('h4 .portal-icon').first().evaluate(el => getComputedStyle(el).color), 'rgb(25, 217, 163)');
                assert.deepEqual(await dialog.locator('.event-poster-time-label').allTextContents(), ['Start', 'End']);
                assert.equal(await dialog.locator('.event-poster-time-row time[datetime]').count(), 2);
                assert(await dialog.locator('.event-poster-help').isVisible());
                assert.equal(await dialog.locator('details, summary').count(), 0);
                assert(await dialog.locator('.event-poster-description').isVisible());
                const left = await dialog.locator('.event-poster-overview').boundingBox();
                const right = await dialog.locator('.event-poster-details').boundingBox();
                if (width >= 650) assert(right.x >= left.x + left.width - 1);
                else assert(right.y >= left.y + left.height - 1);
                await page.keyboard.press('Tab');
                assert(await dialog.evaluate(el => el.contains(document.activeElement)));
                assert(await dialog.locator('.event-schedule').first().isVisible());
                assert(await dialog.evaluate(el => el.scrollWidth <= el.clientWidth + 1));
                await dialog.evaluate(el => el.scrollTop = 0);
                if ([1440, 390, 320].includes(width)) await page.screenshot({ path: `${output}/${theme}-${width}.png` });
                await page.keyboard.press('Escape');
                assert(await page.locator('[data-event-popup]').first().evaluate(el => el === document.activeElement));
                checks.push({ theme, width, ...geometry });
            }
        }
        await open();
        await page.evaluate(() => document.documentElement.dataset.contrast = 'true');
        assert.equal(await dialog.locator('.event-poster-card').evaluate(el => getComputedStyle(el).backgroundColor), 'rgb(255, 255, 255)');
        await page.screenshot({ path: `${output}/high-contrast-320.png` });
        await page.evaluate(() => delete document.documentElement.dataset.contrast);
        await page.emulateMedia({ forcedColors: 'active' });
        assert(await dialog.locator('.event-poster-details').isVisible());
        await page.emulateMedia({ forcedColors: 'none' });
        await dialog.locator('[aria-label="Close details"]').click();
        assert.equal(await page.locator('dialog[open]').count(), 0);

        // Use the real rendered fragment for browser-only long-content and image cases.
        const href = await page.locator('[data-event-popup]').first().getAttribute('href');
        const response = await page.request.get(origin + href + '?popup=1');
        const fragment = await response.text();
        const inject = async html => page.route('**/events/*/?popup=1', route => route.fulfill({ status: 200, contentType: 'text/html', body: html }));
        await inject(fragment.replace(/(<h3[^>]*>)[\s\S]*?(<\/h3>)/, '$1A long community activity title with all event information still readable$2')
            .replace('<div class="event-poster-description" translate="no">', '<div class="event-poster-description" translate="no">' + '<p>Published activity information. </p>'.repeat(25)));
        await open();
        await page.evaluate(() => document.documentElement.style.fontSize = '200%');
        assert(await dialog.evaluate(el => el.scrollHeight > el.clientHeight && el.scrollWidth <= el.clientWidth + 1));
        await dialog.evaluate(el => el.scrollTop = el.scrollHeight);
        assert(await dialog.locator('[aria-label="Close details"]').isVisible());
        await page.screenshot({ path: `${output}/large-text-expanded.png` });
        await page.keyboard.press('Escape');
        await page.evaluate(() => document.documentElement.style.fontSize = '');
        await page.unroute('**/events/*/?popup=1');

        const imageFragment = fragment.replace(/<img[^>]*data-event-poster-image[^>]*>/g, '')
            .replace('<div class="event-poster-artwork">', '<div class="event-poster-artwork"><img src="/static/images/public-association-logo.png" alt="Synthetic artwork check" data-event-poster-image>');
        await inject(imageFragment);
        await open();
        await page.waitForFunction(() => document.querySelector('[data-event-poster-image]').naturalWidth > 0);
        await page.screenshot({ path: `${output}/image-320.png` });
        await page.keyboard.press('Escape');
        await page.unroute('**/events/*/?popup=1');
        await page.route('**/missing-poster.png', route => route.abort());
        await inject(imageFragment.replace('/static/images/public-association-logo.png', '/missing-poster.png'));
        await open();
        await page.waitForFunction(() => document.querySelector('[data-event-poster-image]').hidden);
        await page.keyboard.press('Escape');
        await page.unroute('**/events/*/?popup=1');
        await page.route('**/events/*/?popup=1', route => route.fulfill({ status: 404 }));
        await page.locator('[data-event-popup]').first().click();
        await dialog.getByText('These details could not be loaded.', { exact: false }).waitFor();
        assert(!await dialog.evaluate(el => el.classList.contains('event-poster-dialog')));
        await page.keyboard.press('Escape');
        await page.unroute('**/events/*/?popup=1');
        await page.setViewportSize({ width: 1440, height: 900 });
        await open();
        await page.mouse.click(5, 5);
        assert.equal(await page.locator('dialog[open]').count(), 0);
        const observance = page.locator('[data-public-popup]:not([data-event-popup])').first();
        if (await observance.count()) {
            await observance.click();
            await dialog.locator('[data-public-popup-content]').waitFor();
            assert(!await dialog.evaluate(el => el.classList.contains('event-poster-dialog')));
            await page.keyboard.press('Escape');
        }
        const plain = await browser.newPage({ javaScriptEnabled: false });
        await plain.goto(origin + '/events/');
        await plain.locator('[data-event-popup]').first().click();
        assert(await plain.getByRole('heading', { name: 'About this event' }).isVisible());
        await plain.close();
        assert.deepEqual(errors, []);
        fs.writeFileSync(`${output}/results.json`, JSON.stringify({ checks, visibleSidePanel: true, keyboard: true, closeAndFocusReturn: true, contrast: true, largeText: true, imagesAndFallback: true, errorRecovery: true, observanceIsolation: true, noJavaScript: true, errors }, null, 2));
        console.log('Event poster checks passed: 8 theme/viewport combinations, keyboard, contrast, enlarged text, images, fallback, error recovery and full-page navigation.');
    } finally { await browser.close(); }
})().catch(error => { console.error(error); process.exitCode = 1; });
