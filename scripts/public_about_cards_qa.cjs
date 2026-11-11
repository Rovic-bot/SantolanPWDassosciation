/* Read-only presentation checks; no records are created or changed. */
const { chromium } = require(process.env.PLAYWRIGHT_MODULE || 'C:/Users/rovic/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const origin = process.env.PUBLIC_QA_ORIGIN || 'http://127.0.0.1:8013';
const output = 'docs/public-about-cards-2026-11-08';
const script = fs.readFileSync('static/js/public-about-cards.js', 'utf8');
const normalized = text => text.replace(/\s+/g, ' ').trim();

(async () => {
    const browser = await chromium.launch({ headless: true, executablePath: process.env.CHROME_EXECUTABLE || 'C:/Program Files/Google/Chrome/Application/chrome.exe' });
    try {
        fs.mkdirSync(output, { recursive: true });
        const page = await browser.newPage();
        const errors = [];
        page.on('pageerror', error => errors.push(error.message));
        const checks = [];
        for (const width of [1440, 992, 768, 390, 320]) {
            await page.setViewportSize({ width, height: 900 });
            const response = await page.goto(origin + '/about/');
            assert.equal(response.status(), 200);
            const count = await page.locator('.about-background-card').count();
            assert(count > 1);
            for (let index = 0; index < count; index++) {
                await page.waitForFunction(number => document.querySelector('[data-about-status]').textContent.startsWith(`Card ${number} of`), index + 1);
                assert.equal(await page.locator('.about-background-card:not([hidden])').count(), 1);
                assert.equal(await page.locator('.about-background-card[aria-hidden="false"]').count(), 1);
                assert(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth));
                assert(await page.locator('.about-background-card:not([hidden])').evaluate(el => el.scrollWidth <= el.clientWidth + 1));
                checks.push({ width, card: index + 1, noOverflow: true, onlyCurrentVisible: true });
                if (index === 0 && [1440, 390].includes(width)) await page.screenshot({ path: `${output}/about-${width}.png`, fullPage: true });
                if (index < count - 1) await page.locator('[data-about-next]').click();
            }
            assert.equal(await page.locator('[data-about-next]').getAttribute('aria-disabled'), 'true');
            await page.locator('[data-about-next]').click({ force: true });
            assert((await page.locator('[data-about-status]').textContent()).startsWith(`Card ${count} of`));
            await page.locator('[data-about-viewport]').focus();
            await page.keyboard.press('Home');
            await page.waitForFunction(() => document.querySelector('[data-about-status]').textContent.startsWith('Card 1 of'));
            await page.keyboard.press('ArrowRight');
            await page.waitForFunction(() => document.querySelector('[data-about-status]').textContent.startsWith('Card 2 of'));
            await page.keyboard.press('ArrowLeft');
            await page.waitForFunction(() => document.querySelector('[data-about-status]').textContent.startsWith('Card 1 of'));
        }
        const publishedText = await page.locator('[data-about-viewport] h3,[data-about-viewport] p,[data-about-viewport] li').allTextContents();
        await page.setViewportSize({ width: 1440, height: 900 });
        await page.locator('[data-about-viewport]').scrollIntoViewIfNeeded();
        const box = await page.locator('[data-about-viewport]').boundingBox();
        await page.mouse.move(box.x + box.width * .75, box.y + 80);
        await page.mouse.down();
        await page.mouse.move(box.x + box.width * .25, box.y + 80, { steps: 8 });
        await page.mouse.up();
        const frames = await page.locator('.about-background-card').first().evaluate(el => el.getAnimations().flatMap(a => a.effect.getKeyframes()));
        assert(frames.some(frame => frame.transform === 'translateX(-110%)'), 'Next card sends previous card to the left');
        await page.waitForFunction(() => document.querySelector('[data-about-status]').textContent.startsWith('Card 2 of'));

        // Real browser touch dispatch exercises implicit pointer capture and vertical scrolling.
        const phone = await browser.newPage({ viewport: { width: 390, height: 844 }, hasTouch: true, isMobile: true });
        await phone.goto(origin + '/about/');
        const cdp = await phone.context().newCDPSession(phone);
        async function swipe(dx, dy = 0) {
            await phone.locator('[data-about-viewport]').scrollIntoViewIfNeeded();
            const r = await phone.locator('[data-about-viewport]').boundingBox();
            const x = r.x + r.width * (dx < 0 ? .75 : .25), y = r.y + Math.min(150, r.height / 2);
            await cdp.send('Input.dispatchTouchEvent', { type: 'touchStart', touchPoints: [{ x, y }] });
            for (let step = 1; step <= 6; step++) await cdp.send('Input.dispatchTouchEvent', { type: 'touchMove', touchPoints: [{ x: x + dx * step / 6, y: y + dy * step / 6 }] });
            await cdp.send('Input.dispatchTouchEvent', { type: 'touchEnd', touchPoints: [] });
        }
        await swipe(-120);
        await phone.waitForFunction(() => document.querySelector('[data-about-status]').textContent.startsWith('Card 2 of'));
        await swipe(120);
        await phone.waitForFunction(() => document.querySelector('[data-about-status]').textContent.startsWith('Card 1 of'));
        const scrollBefore = await phone.evaluate(() => scrollY);
        await swipe(0, -100);
        await phone.waitForTimeout(200);
        assert((await phone.locator('[data-about-status]').textContent()).startsWith('Card 1 of'));
        assert(await phone.evaluate(before => scrollY > before, scrollBefore), 'Vertical gestures still scroll the page');
        await phone.close();

        await page.emulateMedia({ reducedMotion: 'reduce' });
        await page.locator('[data-about-next]').click();
        assert.equal(await page.locator('[data-about-viewport]').evaluate(el => el.getAnimations({ subtree: true }).length), 0);
        await page.emulateMedia({ media: 'print' });
        assert.equal(await page.locator('.about-background-card:visible').count(), await page.locator('.about-background-card').count());
        await page.emulateMedia({ media: 'screen' });
        const noScript = await browser.newPage({ javaScriptEnabled: false });
        await noScript.goto(origin + '/about/');
        const plainText = await noScript.locator('[data-about-source] h3,[data-about-source] p,[data-about-source] li').allTextContents();
        assert.deepEqual(plainText.map(normalized), publishedText.map(normalized));
        assert.equal(await noScript.locator('[data-about-controls]').isVisible(), false);
        await noScript.close();

        // A saved plain-text CMS override remains safe and is split by its own headings.
        const sample = await browser.newPage();
        await sample.setContent('<div data-about-carousel><div data-about-viewport><div data-about-source><div class="portal-saved-copy"></div></div></div><div data-about-controls hidden><p data-about-status></p><button data-about-previous></button><button data-about-next></button></div></div>');
        await sample.locator('.portal-saved-copy').evaluate(el => { el.textContent = '## First\n\n<img src=x onerror=alert(1)>\n\n## Second\n\n- Safe item'; });
        await sample.addScriptTag({ content: script });
        assert.equal(await sample.locator('.about-background-card').count(), 2);
        assert.equal(await sample.locator('img').count(), 0);
        assert((await sample.locator('.about-background-card').first().textContent()).includes('<img src=x'));
        await sample.close();
        await page.goto(origin + '/');
        assert.equal(await page.locator('script[src*="public-about-cards"],link[href*="public-about-cards"]').count(), 0);
        assert.deepEqual(errors, []);
        fs.writeFileSync(`${output}/results.json`, JSON.stringify({ checks, errors, mouseAndTouch: true, keyboard: true, reducedMotion: true, contentPreserved: true, printAndNoScript: true, cmsTextEscaped: true }, null, 2));
        console.log(`Passed ${checks.length} card/viewport checks, mouse/touch gestures, keyboard, reduced motion, print, CMS text and no-JavaScript fallback.`);
    } finally { await browser.close(); }
})().catch(error => { console.error(error); process.exitCode = 1; });
