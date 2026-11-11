/* Read-only browser checks for the public portal's shared sidebar and surfaces. */
const { chromium } = require(process.env.PLAYWRIGHT_MODULE || 'C:/Users/rovic/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const origin = process.env.PUBLIC_QA_ORIGIN || 'http://127.0.0.1:8013';
const output = 'docs/public-bento-2026-11-07';
const routes = {
    home: '/', about: '/about/', announcements: '/announcements/', events: '/events/',
    programs: '/programs/', membership: '/membership/register/', resources: '/resources/',
};

(async () => {
    const browser = await chromium.launch({ headless: true, executablePath: process.env.CHROME_EXECUTABLE || 'C:/Program Files/Google/Chrome/Application/chrome.exe' });
    try {
        const page = await browser.newPage();
        const errors = [];
        page.on('pageerror', error => errors.push(error.message));
        const results = [];
        for (const width of [1600, 1440, 1200, 992, 991, 768, 390, 320]) {
            await page.setViewportSize({ width, height: 900 });
            for (const [name, path] of Object.entries(routes)) {
                const response = await page.goto(origin + path);
                await page.locator('.portal-navigation').waitFor();
                const layout = await page.evaluate(() => {
                    const nav = document.querySelector('.portal-navigation');
                    const links = [...nav.querySelectorAll('a')];
                    const rect = nav.getBoundingClientRect();
                    const main = document.querySelector('main').getBoundingClientRect();
                    const h1 = document.querySelector('h1');
                    return {
                        overflow: document.documentElement.scrollWidth > innerWidth + 1,
                        hrefs: links.map(link => link.getAttribute('href')),
                        current: links.filter(link => link.getAttribute('aria-current') === 'page').map(link => link.getAttribute('href')),
                        oldNav: document.querySelectorAll('.bento-top,.bento-rail,.bento-mobile-bottom').length,
                        visibleLinks: links.every(link => {
                            const box = link.getBoundingClientRect();
                            return box.x >= 0 && box.right <= innerWidth && box.y >= 0 && box.bottom <= innerHeight && box.width >= (innerWidth < 360 ? 40 : 44) && box.height >= 44;
                        }),
                        gutter: innerWidth >= 992 ? main.left - rect.right : null,
                        font: getComputedStyle(h1).fontFamily,
                        topPadding: parseFloat(getComputedStyle(document.querySelector('main')).paddingTop),
                        centered: innerWidth < 992 || Math.abs(rect.top + rect.height / 2 - innerHeight / 2) < 1,
                        singleRow: innerWidth >= 992 || new Set(links.map(link => link.getBoundingClientRect().y)).size === 1,
                        hiddenLabels: innerWidth >= 992 || links.every(link => getComputedStyle(link.querySelector('span')).display === 'none'),
                    };
                });
                assert.equal(response.status(), 200, `${name} ${width}`);
                assert.equal(layout.overflow, false, `${name} ${width}: overflow`);
                assert.equal(layout.oldNav, 0);
                assert.deepEqual(layout.hrefs, Object.values(routes));
                assert.deepEqual(layout.current, [path]);
                assert(layout.visibleLinks, `${name} ${width}: nav targets`);
                assert(layout.centered && layout.singleRow && layout.hiddenLabels, `${name} ${width}: centered/sidebar and compact/mobile navigation`);
                assert(layout.gutter === null || layout.gutter >= 24);
                assert(layout.topPadding <= 24);
                assert(layout.font.includes('Arial'));
                results.push({ name, width, status: response.status(), ...layout });
                if ([1440, 390].includes(width)) {
                    await page.screenshot({ path: `${output}/shared-${name}-${width}.png`, fullPage: true });
                }
            }
        }
        // Exercise the same navigation at desktop and phone sizes, including scrolling.
        for (const width of [1440, 390]) {
            await page.setViewportSize({ width, height: 900 });
            await page.goto(origin);
            for (const path of Object.values(routes)) {
                await page.locator(`.portal-navigation a[href="${path}"]`).click();
                assert.equal(new URL(page.url()).pathname, path);
                await page.evaluate(() => window.scrollTo(0, document.body.scrollHeight));
                assert(await page.locator('.portal-navigation').isVisible());
                const box = await page.locator('.portal-navigation').boundingBox();
                assert(box.y >= 0 && box.y + box.height <= 900);
            }
        }
        await page.goto(origin + routes.membership);
        await page.locator('#pdao-tab').click();
        assert(await page.locator('#pdao-service').isVisible());
        await page.locator('#pdao-tab').press('ArrowLeft');
        assert(await page.locator('#association-service').isVisible());
        await page.goto(origin + routes.resources);
        await page.getByText('Do I need an account?', { exact: true }).click();
        assert(await page.locator('#faq details[open]').count() > 0);
        await page.goto(origin + routes.programs);
        assert.equal(await page.locator('.catalog-card').first().evaluate(el => getComputedStyle(el).borderRadius), '30px');
        await page.locator('.catalog-card-link').first().click();
        assert.equal(await page.locator('.portal-navigation [aria-current]').getAttribute('href'), routes.programs);
        await page.goto(origin + routes.events);
        await page.getByRole('button', { name: 'By month', exact: true }).click();
        assert.equal(await page.locator('.portal-observances').getAttribute('data-observance-view'), 'months');
        await page.getByRole('button', { name: 'List view', exact: true }).click();
        await page.locator('.portal-observances').focus();
        await page.keyboard.press('End');
        assert(await page.locator('.portal-observances').evaluate(el => el.scrollTop > 0));
        await page.goto(origin + '/#privacy');
        assert(await page.locator('#privacy').evaluate(el => el.open));
        await page.goto(origin + '/results/');
        assert.equal(await page.locator('.portal-navigation [aria-current]').getAttribute('href'), routes.announcements);
        await page.goto(origin + '/accounts/login/');
        assert.equal(await page.locator('link[href*="public-shell"],.portal-navigation').count(), 0);
        assert.deepEqual(errors, []);
        fs.writeFileSync(`${output}/shared-navigation-results.json`, JSON.stringify({ results, errors, interactions: 'passed' }, null, 2));
        console.log(`Passed ${results.length} responsive route checks, navigation and interaction checks; no page errors.`);
    } finally {
        await browser.close();
    }
})().catch(error => { console.error(error); process.exitCode = 1; });
