/* Image/fallback and theme checks against published announcements; no record writes. */
const { chromium } = require(process.env.PLAYWRIGHT_MODULE || 'C:/Users/rovic/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
const assert = require('node:assert/strict'), fs = require('node:fs');
const origin = process.env.QA_URL || 'http://127.0.0.1:8013';
const output = process.env.QA_OUTPUT || 'docs/public-announcement-portraits-2026-11-09';
(async () => {
    const browser = await chromium.launch({ headless: true, executablePath: process.env.CHROME_EXECUTABLE || 'C:/Program Files/Google/Chrome/Application/chrome.exe' });
    try {
        const page = await browser.newPage(), errors = [], checks = [];
        page.on('pageerror', error => errors.push(error.message));
        fs.mkdirSync(output, { recursive: true });
        for (const theme of ['light', 'dark']) for (const width of [1920, 1440, 768, 390, 320]) {
            await page.setViewportSize({ width, height: 960 });
            await page.goto(origin + '/announcements/');
            await page.evaluate(theme => document.documentElement.dataset.publicTheme = theme, theme);
            await page.waitForSelector('.notice-swipe-carousel.is-ready');
            const deck = page.locator('.notice-swipe-carousel');
            await deck.scrollIntoViewIfNeeded();
            await page.locator('.notice-row:not([hidden]) img').evaluateAll(images => Promise.all(images.map(img => img.decode().catch(() => {}))));
            const data = await page.locator('.notice-row:not([hidden])').evaluateAll(cards => cards.map(card => {
                const footer = card.querySelector('.notice-card-footer').getBoundingClientRect(), rect = card.getBoundingClientRect();
                const image = card.querySelector('img[data-notice-image]'), initials = card.querySelector('.notice-card-initials');
                return { title: card.querySelector('h3').textContent.trim(), width: rect.width, height: rect.height, footerFits: footer.bottom <= rect.bottom && footer.right <= rect.right, overflow: card.scrollWidth - card.clientWidth, imageLoaded: image ? image.naturalWidth > 0 : null, initials: initials.textContent.trim() };
            }));
            assert(data.every(card => card.footerFits && card.overflow <= 1 && card.initials));
            assert(data.every(card => card.imageLoaded !== false));
            assert(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1));
            if (width >= 1440) assert(data.length >= 4);
            await deck.screenshot({ path: `${output}/portraits-${theme}-${width}.png` });
            checks.push({ theme, width, cards: data });
        }
        const imageURL = await page.locator('[data-notice-image]').first().getAttribute('src');
        await page.route('**' + imageURL, route => route.abort());
        await page.reload();
        const failed = page.locator('.notice-row').filter({ has: page.locator('[data-notice-image]') }).first();
        for (let attempt = 0; attempt < 24 && !await failed.isVisible(); attempt++) {
            const status = page.locator('.notice-swipe-carousel [data-swipe-status]');
            const before = await status.textContent();
            await page.locator('.notice-swipe-carousel [data-swipe-next]').click();
            await page.waitForFunction(before => document.querySelector('.notice-swipe-carousel [data-swipe-status]').textContent !== before, before);
        }
        await page.waitForFunction(() => document.querySelector('[data-notice-image]')?.hidden);
        assert(await failed.locator('.notice-card-initials').isVisible());
        await failed.screenshot({ path: `${output}/failed-image-initials.png` });
        // Filtering inserts fresh cards; the same failure fallback must still work.
        await page.locator('.notice-topic-links a').filter({ hasText: /^Announcements$/ }).click();
        await page.waitForFunction(() => document.querySelector('.public-browse-status')?.textContent === 'Results updated.' && !document.querySelector('[data-public-browser][aria-busy]'));
        await page.waitForFunction(() => document.querySelector('[data-notice-image]')?.hidden);
        assert(await page.locator('.notice-row .notice-card-initials').first().isVisible());
        await page.evaluate(() => document.documentElement.dataset.contrast = 'true');
        assert.equal(await page.locator('.notice-card-artwork').first().evaluate(el => getComputedStyle(el).display), 'none');
        await page.locator('.notice-swipe-carousel').screenshot({ path: `${output}/contrast-320.png` });
        await page.evaluate(() => delete document.documentElement.dataset.contrast);
        await page.emulateMedia({ forcedColors: 'active' });
        assert.equal(await page.locator('.notice-card-artwork').first().evaluate(el => getComputedStyle(el).display), 'none');
        await page.emulateMedia({ forcedColors: 'none' });
        await page.locator('.notice-row-action').first().click();
        await page.waitForSelector('.announcement-poster-dialog .announcement-poster');
        assert.equal(await page.locator('.announcement-poster-action').count(), 0);
        await page.keyboard.press('Escape');
        assert.deepEqual(errors, []);
        fs.writeFileSync(`${output}/image-theme-results.json`, JSON.stringify({ checks, failedImage: true, dynamicFallback: true, contrast: true, popup: true, errors }, null, 2));
        console.log('Portrait cards passed: ten theme/viewport combinations, published images, initials, failed/dynamic image fallback, contrast and popup.');
    } finally { await browser.close(); }
})().catch(error => { console.error(error); process.exitCode = 1; });
