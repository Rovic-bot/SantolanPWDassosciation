/* Read-only public presentation checks. No application records are changed. */
const { chromium } = require(process.env.PLAYWRIGHT_MODULE || 'C:/Users/rovic/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const origin = process.env.PUBLIC_QA_ORIGIN || 'http://127.0.0.1:8013';
const output = 'docs/public-swipe-2026-11-08';
const pages = [['/', 1], ['/about/', 1], ['/resources/', 2]];
const deckSelector = '.public-swipe-carousel.is-ready';
const viewportSelector = '.public-swipe-viewport';

(async () => {
    const browser = await chromium.launch({ headless: true, executablePath: process.env.CHROME_EXECUTABLE || 'C:/Program Files/Google/Chrome/Application/chrome.exe' });
    try {
        fs.mkdirSync(output, { recursive: true });
        const page = await browser.newPage();
        await page.emulateMedia({ reducedMotion: 'reduce' });
        const errors = [];
        page.on('pageerror', error => errors.push(error.message));
        const checks = [];
        async function waitForCard(deck, number) {
            await deck.locator('.public-swipe-count').filter({ hasText: new RegExp(`^Card ${number} of`) }).waitFor();
            assert.equal(await deck.locator('.public-swipe-card:not([hidden])').count(), 1);
        }
        for (const width of [1440, 768, 390, 320]) {
            await page.setViewportSize({ width, height: 900 });
            for (const [path, expectedDecks] of pages) {
                assert.equal((await page.goto(origin + path)).status(), 200);
                const decks = page.locator(deckSelector);
                assert.equal(await decks.count(), expectedDecks);
                assert.equal(await page.locator('dialog[data-guidance-dialog], [data-guidance-open]').count(), 0);
                assert.equal(await page.locator('.portal-navigation [aria-current="page"]').count(), 1);
                for (const deck of await decks.all()) {
                    const count = await deck.locator('.public-swipe-card').count();
                    const height = await deck.evaluate(el => el.getBoundingClientRect().height);
                    for (let card = 1; card <= count; card++) {
                        await waitForCard(deck, card);
                        assert.equal(await deck.locator(viewportSelector).evaluate(el => el.getBoundingClientRect().height), 320);
                        assert.equal(await deck.evaluate(el => el.getBoundingClientRect().height), height);
                        assert(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth));
                        assert(await deck.locator('.public-swipe-card:not([hidden])').evaluate(el => el.scrollWidth <= el.clientWidth + 1));
                        assert.equal(await deck.locator('.public-swipe-card[aria-hidden="false"]').count(), 1);
                        checks.push({ path, width, deck: await deck.getAttribute('aria-labelledby'), card, fixedHeight: height });
                        if (card < count) await deck.locator('[data-about-next], [data-swipe-next]').click();
                    }
                    assert.equal(await deck.locator('[data-about-next], [data-swipe-next]').getAttribute('aria-disabled'), 'true');
                    await deck.locator(viewportSelector).focus();
                    await page.keyboard.press('Home');
                    await waitForCard(deck, 1);
                    await page.keyboard.press('ArrowRight');
                    await waitForCard(deck, 2);
                    await page.keyboard.press('ArrowLeft');
                    await waitForCard(deck, 1);
                }
                if ([1440, 390].includes(width)) {
                    await page.evaluate(() => window.scrollTo({ top: 0, behavior: 'instant' }));
                    await page.screenshot({ path: `${output}/${path.split('/')[1] || 'home'}-${width}.png`, fullPage: true });
                }
                console.log(`Fixed heights and keyboard: ${path} at ${width}px`);
            }
        }
        // Real touch dispatch checks child pointer capture on every type of deck.
        const phone = await browser.newPage({ viewport: { width: 390, height: 844 }, hasTouch: true, isMobile: true });
        phone.on('pageerror', error => errors.push(error.message));
        const cdp = await phone.context().newCDPSession(phone);
        async function swipe(deck, dx, dy = 0) {
            const viewport = deck.locator(viewportSelector);
            await viewport.scrollIntoViewIfNeeded();
            // Links and buttons stay tappable; begin the swipe on card copy or empty space.
            const point = await viewport.evaluate((el, forward) => {
                const r = el.getBoundingClientRect();
                const x = r.x + r.width * (forward ? .8 : .2);
                for (const offset of [110, 170, 230, 280]) {
                    const y = r.y + offset, target = document.elementFromPoint(x, y);
                    if (el.contains(target) && !target.closest('a,button,input,select,textarea')) return { x, y };
                }
                return null;
            }, dx < 0);
            assert(point, 'Card must have a non-interactive area to swipe');
            const { x, y } = point;
            await cdp.send('Input.dispatchTouchEvent', { type: 'touchStart', touchPoints: [{ x, y }] });
            for (let step = 1; step <= 6; step++) await cdp.send('Input.dispatchTouchEvent', { type: 'touchMove', touchPoints: [{ x: x + dx * step / 6, y: y + dy * step / 6 }] });
            await cdp.send('Input.dispatchTouchEvent', { type: 'touchEnd', touchPoints: [] });
        }
        for (const [path] of pages) {
            await phone.goto(origin + path);
            for (const deck of await phone.locator(deckSelector).all()) {
                await swipe(deck, -120);
                await waitForCard(deck, 2);
                await swipe(deck, 120);
                await waitForCard(deck, 1);
            }
            if (path === '/') {
                const deck = phone.locator(deckSelector).first();
                await swipe(deck, 0, -100);
                await phone.waitForTimeout(200);
                await waitForCard(deck, 1);
                assert(await deck.locator('.public-swipe-card:not([hidden])').evaluate(el => el.scrollTop > 0));
            }
            console.log(`Touch gestures: ${path}`);
        }
        await phone.close();
        // Existing links reveal the correct card instead of a dialog.
        for (const [path, target] of [['/#privacy', '#privacy'], ['/#ewaf', '#ewaf'], ['/resources/#resources-accessibility', '#resources-accessibility']]) {
            await page.goto(origin + path);
            assert.equal(await page.locator(target).isVisible(), true);
            assert.equal(await page.locator(target).getAttribute('aria-hidden'), 'false');
            assert.equal(await page.locator('dialog[open]').count(), 0);
        }
        for (const path of ['/contact/', '/#contact', '/assistance/referrals/']) {
            await page.goto(origin + path);
            await page.waitForURL(origin + '/resources/#referral-support');
            assert.equal(await page.locator('#referral-support').isVisible(), true);
            assert.equal(await page.locator('dialog[open]').count(), 0);
            assert.equal(await page.getByText('Read the guidance first', { exact: true }).count(), 0);
        }
        await page.goto(origin + '/');
        await page.locator('.home-support-card a').click();
        await page.waitForURL(origin + '/resources/#referral-support');
        await page.goto(origin + '/programs/');
        assert.equal(await page.getByText('Search and filter programs', { exact: true }).count(), 0);
        await page.goto(origin + '/announcements/');
        assert.deepEqual((await page.locator('.notice-topic-links a').allTextContents()).map(text => text.trim()), ['All', 'Announcements', 'Program Results']);
        for (const category of ['announcements', 'results']) {
            await page.goto(origin + '/announcements/?category=' + category);
            assert.equal(await page.locator('.notice-topic-links [aria-current="page"]').count(), 1);
        }
        // Event grid, click-anywhere popup, keyboard close and stale-publication failure.
        await page.setViewportSize({ width: 1440, height: 900 });
        await page.goto(origin + '/events/');
        const grid = page.locator('.portal-event-grid');
        assert.equal(await grid.evaluate(el => getComputedStyle(el).gridTemplateColumns.split(' ').length), 3);
        const eventLink = page.locator('[data-event-popup]').first();
        const eventUrl = await eventLink.getAttribute('href');
        assert(eventUrl, 'At least one published event is needed for read-only browser QA');
        await page.locator('.portal-event-card').first().click({ position: { x: 20, y: 20 } });
        const dialog = page.locator('[data-event-dialog]');
        await dialog.locator('[data-event-content]').waitFor();
        assert.equal(await dialog.isVisible(), true);
        assert(await page.evaluate(() => document.querySelector('dialog[open]').contains(document.activeElement)));
        await page.keyboard.press('Shift+Tab');
        assert(await page.evaluate(() => document.querySelector('dialog[open]').contains(document.activeElement)));
        await page.screenshot({ path: `${output}/event-popup-1440.png` });
        await page.keyboard.press('Escape');
        assert.equal(await dialog.isVisible(), false);
        assert.equal(await eventLink.evaluate(el => el === document.activeElement), true);
        await page.setViewportSize({ width: 320, height: 900 });
        await eventLink.click();
        await dialog.locator('[data-event-content]').waitFor();
        assert(await dialog.evaluate(el => el.scrollWidth <= el.clientWidth + 1));
        await page.screenshot({ path: `${output}/event-popup-320.png` });
        await dialog.locator('button').first().click();
        await page.route('**' + eventUrl + '?popup=1', route => route.fulfill({ status: 404, body: 'No longer public' }));
        await eventLink.click();
        await dialog.getByText('This event could not be loaded. It may no longer be published.').waitFor();
        assert.equal(await dialog.locator('[data-event-content]').count(), 0);
        await page.keyboard.press('Escape');
        // Motion preference, long-copy scrolling and readable no-script/print fallbacks.
        await page.goto(origin + '/resources/');
        await page.emulateMedia({ reducedMotion: 'reduce' });
        const faq = page.locator(deckSelector).first();
        await faq.locator('[data-swipe-next]').click();
        await waitForCard(faq, 2);
        assert.equal(await faq.evaluate(el => el.getAnimations({ subtree: true }).length), 0);
        assert(await faq.locator('.public-swipe-card:not([hidden])').evaluate(el => el.scrollHeight > el.clientHeight));
        await faq.locator('.public-swipe-card:not([hidden])').evaluate(el => { el.scrollTop = el.scrollHeight; });
        assert(await faq.locator('.public-swipe-card:not([hidden])').evaluate(el => el.scrollTop > 0));
        await page.emulateMedia({ media: 'print' });
        assert.equal(await page.locator('.public-swipe-card:visible').count(), await page.locator('.public-swipe-card').count());
        const plain = await browser.newPage({ javaScriptEnabled: false });
        for (const path of ['/', '/resources/']) {
            await plain.goto(origin + path);
            assert.equal(await plain.locator('[data-swipe-card]:visible').count(), await plain.locator('[data-swipe-card]').count());
            assert.equal(await plain.locator('[data-swipe-controls]:visible').count(), 0);
        }
        await plain.goto(origin + '/events/');
        await plain.locator('[data-event-popup]').first().click();
        assert.equal(new URL(plain.url()).pathname, eventUrl);
        assert.equal(await plain.locator('[data-event-dialog]').count(), 0);
        await plain.close();
        assert.deepEqual(errors, []);
        fs.writeFileSync(`${output}/results.json`, JSON.stringify({ checks, errors, touch: true, keyboard: true, fixedHeights: true, redirects: true, eventPopup: true, unpublishedError: true, noScriptAndPrint: true }, null, 2));
        console.log(`Passed ${checks.length} fixed-height card checks, touch/keyboard navigation, redirects, event popup and fallback checks.`);
    } finally { await browser.close(); }
})().catch(error => { console.error(error); process.exitCode = 1; });
