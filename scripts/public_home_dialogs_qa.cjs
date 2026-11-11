/* Read-only checks for native guidance dialogs and Home cards. */
const { chromium } = require(process.env.PLAYWRIGHT_MODULE || 'C:/Users/rovic/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const origin = process.env.PUBLIC_QA_ORIGIN || 'http://127.0.0.1:8013';
const output = 'docs/public-bento-2026-11-07';
const anchors = ['application-information', 'contact', 'faq', 'ewaf', 'privacy', 'accessibility'];

(async () => {
    const browser = await chromium.launch({ headless: true, executablePath: process.env.CHROME_EXECUTABLE || 'C:/Program Files/Google/Chrome/Application/chrome.exe' });
    try {
        const page = await browser.newPage();
        const errors = [];
        page.on('pageerror', error => errors.push(error.message));
        const checks = [];
        for (const width of [1440, 992, 768, 390, 320]) {
            await page.setViewportSize({ width, height: 900 });
            await page.goto(origin);
            assert.equal(await page.locator('.home-guidance-dialog[open]').count(), 0);
            assert.equal(await page.locator('.home-guidance-trigger').count(), 6);
            assert.equal(await page.locator('.home-feature-grid > *').count(), 3);
            assert(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth));
            assert(await page.locator('.home-feature-grid > *').evaluateAll(cards => cards.every(card => card.scrollWidth <= card.clientWidth + 1)));
            for (const anchor of anchors) {
                const trigger = page.locator(`.home-guidance-trigger[href="#${anchor}"]`);
                const dialog = page.locator(`#${anchor}`);
                await trigger.click();
                assert(await dialog.evaluate(el => el.open && el.matches(':modal')));
                assert.equal(await page.locator('dialog[open]').count(), 1);
                assert(await dialog.evaluate(el => el.contains(document.activeElement)));
                assert(await dialog.evaluate(el => el.getBoundingClientRect().height <= innerHeight && el.scrollWidth <= el.clientWidth + 1));
                // Native modal navigation cannot focus the page behind it.
                await page.keyboard.press('Shift+Tab');
                await page.keyboard.press('Tab');
                assert(await dialog.evaluate(el => el.contains(document.activeElement)));
                if (anchor === 'privacy' && [1440, 390, 320].includes(width)) {
                    await page.screenshot({ path: `${output}/privacy-dialog-${width}.png` });
                }
                await page.keyboard.press('Escape');
                await page.waitForFunction(id => !document.getElementById(id).open && location.hash === '', anchor);
                assert(await trigger.evaluate(el => el === document.activeElement));
                checks.push({ width, anchor, modal: true, escape: true, focusReturned: true });
            }
            await page.goto(origin + '/#privacy');
            await page.waitForFunction(() => document.querySelector('#privacy').open);
            await page.locator('#privacy .home-guidance-close').click();
            await page.waitForFunction(() => !document.querySelector('#privacy').open);
            await page.locator('.home-guidance-trigger[href="#faq"]').click();
            await page.mouse.click(2, 2);
            await page.waitForFunction(() => !document.querySelector('#faq').open);
            await page.evaluate(() => window.scrollTo(0, 0));
            if ([1440, 390, 320].includes(width)) await page.screenshot({ path: `${output}/home-dialogs-${width}.png`, fullPage: true });
        }
        await page.goto(origin + '/contact/');
        await page.waitForFunction(() => document.querySelector('#contact').open);
        await page.keyboard.press('Escape');
        await page.locator('.home-support-card > a').click();
        assert(await page.locator('#contact').evaluate(el => el.open));
        await page.goBack();
        await page.waitForFunction(() => !document.querySelector('#contact').open);
        const noScript = await browser.newPage({ javaScriptEnabled: false, viewport: { width: 390, height: 900 } });
        await noScript.goto(origin);
        for (const anchor of anchors) assert(await noScript.locator(`#${anchor}`).isVisible(), `${anchor} is readable without JavaScript`);
        await noScript.close();
        assert.deepEqual(errors, []);
        fs.writeFileSync(`${output}/home-dialogs-results.json`, JSON.stringify({ checks, errors, deepLinks: true, noScript: true }, null, 2));
        console.log(`Passed ${checks.length} popup checks, responsive cards, bookmarks, backdrop/close buttons, browser Back and no-JavaScript fallback.`);
    } finally {
        await browser.close();
    }
})().catch(error => { console.error(error); process.exitCode = 1; });
