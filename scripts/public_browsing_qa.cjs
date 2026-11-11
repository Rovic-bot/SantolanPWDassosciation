/* Public browsing and private editor preview checks. Never saves portal content. */
const { chromium } = require(process.env.PLAYWRIGHT_MODULE || 'C:/Users/rovic/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const origin = process.env.PUBLIC_QA_ORIGIN || 'http://127.0.0.1:8013';
const output = 'docs/public-browsing-2026-11-08';

(async () => {
    const browser = await chromium.launch({ headless: true, executablePath: process.env.CHROME_EXECUTABLE || 'C:/Program Files/Google/Chrome/Application/chrome.exe' });
    try {
        fs.mkdirSync(output, { recursive: true });
        const page = await browser.newPage({ viewport: { width: 1440, height: 960 }, reducedMotion: 'reduce' });
        const errors = [], checks = [];
        page.on('pageerror', e => errors.push(e.message));
        for (const width of [1440, 768, 390, 320]) {
            await page.setViewportSize({ width, height: 960 });
            for (const path of ['/', '/about/', '/resources/', '/programs/', '/announcements/', '/events/']) {
                assert.equal((await page.goto(origin + path)).status(), 200);
                assert(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth));
                for (const deck of await page.locator('.public-swipe-carousel.is-ready').all()) {
                    const viewport = deck.locator('.public-swipe-viewport');
                    const count = await deck.locator('.public-swipe-card').count();
                    const visible = await deck.locator('.public-swipe-card:not([hidden])').count();
                    assert(visible >= 1 && visible <= count);
                    assert(await viewport.evaluate(el => [...el.querySelectorAll('.public-swipe-card:not([hidden])')].every(card => card.scrollHeight <= card.clientHeight + 1)));
                    const height = await deck.evaluate(el => el.getBoundingClientRect().height);
                    const first = await deck.locator('.public-swipe-count').textContent();
                    if (count > visible) {
                        await deck.locator('[data-swipe-next], [data-about-next]').click();
                        await page.waitForFunction(({ id, first }) => document.getElementById(id).closest('.public-swipe-carousel').querySelector('.public-swipe-count').textContent !== first,
                            { id: await viewport.getAttribute('id'), first });
                        assert.equal(await deck.evaluate(el => el.getBoundingClientRect().height), height);
                        await viewport.focus(); await page.keyboard.press('Home');
                        await page.waitForFunction(({ id, first }) => document.getElementById(id).closest('.public-swipe-carousel').querySelector('.public-swipe-count').textContent === first,
                            { id: await viewport.getAttribute('id'), first });
                    }
                    checks.push({ path, width, visibleCards: visible, fixedHeight: true });
                }
                if ([1440, 390].includes(width)) {
                    await page.evaluate(() => { document.activeElement?.blur(); scrollTo({ top: 0, behavior: 'instant' }); });
                    await page.screenshot({ path: `${output}/${path.split('/')[1] || 'home'}-${width}.png`, fullPage: true });
                }
            }
            console.log(`Responsive cards and layout: ${width}px`);
        }
        await page.setViewportSize({ width: 1440, height: 960 });
        let documentRequests = 0;
        page.on('request', request => { if (request.isNavigationRequest() && request.frame() === page.mainFrame()) documentRequests++; });
        async function inPlace(action, prepare) {
            if (prepare) await prepare();
            const before = await page.evaluate(() => ({ y: scrollY, marker: window.publicQAMarker ||= Math.random() }));
            const requests = documentRequests;
            await action();
            await page.waitForFunction(() => document.querySelector('.public-browse-status')?.textContent === 'Results updated.' && !document.querySelector('[data-public-browser][aria-busy]'));
            assert.equal(documentRequests, requests, 'Filters must not navigate the document');
            assert.equal(await page.evaluate(() => window.publicQAMarker), before.marker);
            assert(Math.abs(await page.evaluate(() => scrollY) - before.y) < 2, 'Viewport must remain in place');
        }
        await page.goto(origin + '/programs/');
        const next = page.locator('.catalog-pagination [rel=next]');
        await inPlace(() => next.click(), () => next.scrollIntoViewIfNeeded());
        assert.equal(new URL(page.url()).searchParams.get('page'), '2');
        const pageTwoY = await page.evaluate(() => scrollY);
        await page.goBack();
        await page.waitForFunction(() => !document.querySelector('[data-public-browser][aria-busy]') && !location.search.includes('page=2'));
        assert(Math.abs(await page.evaluate(() => scrollY) - pageTwoY) < 2);
        const open = page.locator('.catalog-tab').filter({ hasText: /^Open/ });
        await inPlace(() => open.click(), () => open.scrollIntoViewIfNeeded());
        assert.equal(new URL(page.url()).searchParams.get('period'), 'available');
        assert.equal(await page.getByText('More about verification and selection', { exact: true }).count(), 0);
        const detailHref = await page.locator('.catalog-card-link').first().getAttribute('href');
        await page.goto(origin + detailHref);
        assert.equal(await page.locator('.public-program-artwork--detail').count(), 1);
        assert.equal(await page.locator('.public-program-artwork--detail img:visible, .public-program-artwork--detail .public-program-initials:visible').count(), 1);
        await page.screenshot({ path: `${output}/program-detail-1440.png`, fullPage: true });
        await page.goto(origin + '/announcements/');
        const results = page.locator('.notice-topic-links a').filter({ hasText: 'Program Results' });
        await inPlace(() => results.click(), async () => { await results.scrollIntoViewIfNeeded(); await page.evaluate(() => scrollTo({ top: 100, behavior: 'instant' })); });
        assert.equal(new URL(page.url()).searchParams.get('category'), 'results');
        await page.locator('#announcement-search').fill('no-such-public-notice-qa');
        const search = page.locator('.notice-search button');
        await inPlace(() => search.click(), () => search.scrollIntoViewIfNeeded());
        assert.equal(await page.locator('.notice-empty').count(), 1);
        const all = page.locator('.notice-empty a');
        await inPlace(() => all.click(), () => all.scrollIntoViewIfNeeded());
        async function popup(trigger, title) {
            await trigger.scrollIntoViewIfNeeded();
            const location = page.url(), y = await page.evaluate(() => scrollY);
            await trigger.click();
            const dialog = page.locator('[data-public-dialog]');
            await dialog.locator('[data-public-popup-content], [data-event-content]').waitFor();
            assert.equal(page.url(), location);
            assert.equal(await dialog.locator('[data-public-dialog-title]').textContent(), title);
            assert(await dialog.evaluate(el => el.contains(document.activeElement)));
            await page.keyboard.press('Shift+Tab');
            assert(await dialog.evaluate(el => el.contains(document.activeElement)));
            await page.screenshot({ path: `${output}/${title.toLowerCase().replaceAll(' ', '-')}.png` });
            await page.keyboard.press('Escape');
            assert.equal(await dialog.isVisible(), false);
            assert.equal(await trigger.evaluate(el => el === document.activeElement), true);
            assert(Math.abs(await page.evaluate(() => scrollY) - y) < 2);
        }
        await popup(page.locator('.notice-row-action').first(), 'Announcement details');
        await page.goto(origin + '/events/');
        const formButton = page.locator('.portal-filter-bar button');
        await page.locator('#event-period').selectOption('past');
        await inPlace(() => formButton.click(), () => formButton.scrollIntoViewIfNeeded());
        await page.locator('#event-period').selectOption('upcoming');
        await inPlace(() => formButton.click());
        await popup(page.locator('[data-event-popup]').first(), 'Event details');
        await popup(page.locator('.observance-swipe-card [data-public-popup]').first(), 'Observance details');
        assert.equal(await page.getByText('DATES FOR AWARENESS', { exact: true }).count(), 0);
        assert.equal(await page.getByRole('heading', { name: 'Annual observances', exact: true }).count(), 0);
        // Network errors leave the current page and its scroll position intact.
        await page.route('**/events/?period=past', route => route.fulfill({ status: 503, body: 'Unavailable' }));
        await page.locator('#event-period').selectOption('past');
        await formButton.scrollIntoViewIfNeeded();
        const oldY = await page.evaluate(() => scrollY), oldURL = page.url();
        await formButton.click();
        await page.getByText('The results could not be updated. Please try the filter again.').waitFor();
        assert.equal(page.url(), oldURL);
        assert(Math.abs(await page.evaluate(() => scrollY) - oldY) < 2);
        console.log('Pagination, filters, browser Back, dialogs and network failure passed');
        const phone = await browser.newPage({ viewport: { width: 390, height: 844 }, hasTouch: true, isMobile: true });
        const cdp = await phone.context().newCDPSession(phone);
        for (const path of ['/', '/events/']) {
            await phone.goto(origin + path);
            const deck = phone.locator('.public-swipe-carousel.is-ready').first();
            const viewport = deck.locator('.public-swipe-viewport');
            await viewport.scrollIntoViewIfNeeded();
            const start = await viewport.evaluate(el => {
                const r = el.getBoundingClientRect(), x = r.x + r.width * .8;
                for (const offset of [110, 170, 230, 280]) {
                    const y = r.y + offset, target = document.elementFromPoint(x, y);
                    if (el.contains(target) && !target.closest('a,button')) return { x, y };
                }
            });
            const first = await deck.locator('.public-swipe-count').textContent();
            await cdp.send('Input.dispatchTouchEvent', { type: 'touchStart', touchPoints: [start] });
            for (let step = 1; step <= 6; step++) await cdp.send('Input.dispatchTouchEvent', { type: 'touchMove', touchPoints: [{ x: start.x - 120 * step / 6, y: start.y }] });
            await cdp.send('Input.dispatchTouchEvent', { type: 'touchEnd', touchPoints: [] });
            await phone.waitForFunction(first => document.querySelector('.public-swipe-count').textContent !== first, first);
        }
        await phone.close();
        // Exercise the actual admin image button and editable cards without saving.
        const admin = await browser.newPage({ viewport: { width: 1440, height: 960 } });
        admin.on('pageerror', e => errors.push(e.message));
        admin.on('dialog', dialog => dialog.accept());
        const login = fs.readFileSync('.local/ewaf-twelve-demo/LOGIN.txt', 'utf8');
        await admin.goto(origin + '/accounts/login/');
        await admin.locator('[name=username]').fill(login.match(/^Username:\s*(.+)$/m)[1].trim());
        await admin.locator('[name=password]').fill(login.match(/^Password:\s*(.+)$/m)[1].trim());
        await admin.locator('button[type=submit]').click();
        await admin.goto(origin + '/content/');
        const frame = admin.frameLocator('[data-editor-frame]');
        await frame.locator('body[data-portal-editing=true]').waitFor();
        await frame.locator('[data-portal-picture="picture_1"] .portal-picture-action').click();
        await admin.locator('[data-editor-picture-dialog][open]').waitFor();
        await admin.screenshot({ path: `${output}/admin-home-image-control.png` });
        await admin.locator('[data-picture-file]').setInputFiles('static/images/public-association-logo.png');
        await admin.locator('[data-picture-alt]').fill('Preview-only association image');
        await admin.locator('[data-picture-apply]').click();
        await frame.locator('[data-portal-picture="picture_1"] img[src^="blob:"]').waitFor();
        await admin.locator('[data-editor-save]:not([disabled])').waitFor();
        await admin.locator('[data-editor-discard]').click();
        await frame.locator('body[data-portal-editing=true]').waitFor();
        for (const field of ['guidance_heading', 'guidance_application-information', 'guidance_faq', 'guidance_title_faq']) {
            assert.equal(await frame.locator(`[data-portal-field="${field}"]`).getAttribute('contenteditable'), 'plaintext-only');
        }
        await frame.locator('[data-portal-field="guidance_heading"]').fill('Preview-only guidance heading');
        await admin.locator('[data-editor-save]:not([disabled])').waitFor();
        await admin.locator('[data-editor-discard]').click();
        await frame.locator('body[data-portal-editing=true]').waitFor();
        await admin.locator('[data-editor-page=resources]').click();
        await frame.locator('[data-portal-field="resource_body_resources-care"]').waitFor();
        for (const field of ['text_012', 'text_015', 'text_028', 'resource_title_resources-work', 'resource_body_resources-care', 'faq_membership_description', 'faq_pdao_description', 'faq_program_description', 'faq_referral_description']) {
            assert.equal(await frame.locator(`[data-portal-field="${field}"]`).getAttribute('contenteditable'), 'plaintext-only');
        }
        assert.equal(await frame.locator('.public-swipe-card[hidden]').count(), 0);
        await admin.close();
        assert.deepEqual(errors, []);
        fs.writeFileSync(`${output}/results.json`, JSON.stringify({ checks, errors, inPlaceNavigation: true, popupFocusAndPublication: true, touch: true, adminPreview: true, contentSaved: false, imagePreviewAndDiscard: true }, null, 2));
        console.log(`Passed ${checks.length} responsive deck checks, in-place browsing, popups, touch and admin content controls.`);
    } finally { await browser.close(); }
})().catch(error => { console.error(error); process.exitCode = 1; });
