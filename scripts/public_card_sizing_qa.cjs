/* Content-driven public cards: no internal scrolling and no saved content changes. */
const { chromium } = require(process.env.PLAYWRIGHT_MODULE || 'C:/Users/rovic/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const origin = process.env.PUBLIC_QA_ORIGIN || 'http://127.0.0.1:8013';
const output = 'docs/public-card-sizing-2026-11-08';
(async () => {
  const browser = await chromium.launch({ headless: true, executablePath: process.env.CHROME_EXECUTABLE || 'C:/Program Files/Google/Chrome/Application/chrome.exe' });
  try {
    fs.mkdirSync(output, { recursive: true });
    const page = await browser.newPage({ reducedMotion: 'reduce' });
    const errors = [], checks = [];
    page.on('pageerror', error => errors.push(error.message));
    async function inspectDeck(deck) {
      const viewport = deck.locator('.public-swipe-viewport');
      const height = await viewport.evaluate(el => el.getBoundingClientRect().height);
      const count = await deck.locator('.public-swipe-card').count();
      const seen = new Set(), sizes = [];
      const next = deck.locator('[data-swipe-next], [data-about-next]');
      for (let attempt = 0; attempt <= count; attempt++) {
        const visible = await viewport.evaluate(el => {
          const boundary = el.getBoundingClientRect();
          const cards = [...el.querySelectorAll('.public-swipe-card:not([hidden])')];
          const centered = Math.abs((cards[0].getBoundingClientRect().left + cards.at(-1).getBoundingClientRect().right) / 2 - (boundary.left + boundary.right) / 2) <= 1;
          return cards.map(card => {
            const r = card.getBoundingClientRect();
            return { label: card.getAttribute('aria-label'), width: r.width, height: r.height,
              overflow: card.scrollHeight - card.clientHeight, scrollStyle: getComputedStyle(card).overflowY, eventCard: card.classList.contains('event-photo-card'),
              fits: r.left >= boundary.left - 1 && r.right <= boundary.right + 1,
              centered, inert: card.inert, hidden: card.getAttribute('aria-hidden') };
          });
        });
        assert(visible.length);
        for (const card of visible) {
          assert.equal(card.scrollStyle, card.eventCard ? 'hidden' : 'visible');
          assert(card.overflow <= 1, `Clipped text: ${JSON.stringify(card)}`);
          assert(Math.abs(card.height - height) <= 1, 'All cards share the same stable row height');
          assert(card.fits && !card.inert && card.hidden === 'false');
          assert(card.centered, 'Visible cards must be centered as a group');
          seen.add(card.label); sizes.push(card.width);
        }
        assert.equal(await viewport.evaluate(el => el.getBoundingClientRect().height), height);
        if (await next.getAttribute('aria-disabled') === 'true') break;
        const before = await deck.locator('.public-swipe-count').textContent();
        await next.click();
        await page.waitForFunction(({id,before}) => document.getElementById(id).closest('.public-swipe-carousel').querySelector('.public-swipe-count').textContent !== before, {id:await viewport.getAttribute('id'),before});
      }
      assert.equal(seen.size, count, 'Every card remains reachable');
      await viewport.focus(); await page.keyboard.press('Home');
      await page.waitForFunction(id => document.getElementById(id).closest('.public-swipe-carousel').querySelector('[data-swipe-previous], [data-about-previous]').getAttribute('aria-disabled') === 'true', await viewport.getAttribute('id'));
      return { height, cards: count, widths: sizes.map(value => Math.round(value)) };
    }
    for (const width of [1920,1440,992,768,390,320]) {
      await page.setViewportSize({width,height:960});
      for (const path of ['/', '/about/', '/resources/', '/events/']) {
        await page.goto(origin + path);
        await page.evaluate(async()=>{await document.fonts.ready; await new Promise(requestAnimationFrame);});
        if (path === '/about/') {
          const first = page.locator('.public-swipe-card').first();
          assert.deepEqual(await first.locator('h3').allTextContents(), ['Background', 'Our mission']);
          assert.equal(await page.locator('.public-swipe-card').count(), 6);
        }
        if (path === '/resources/') {
          assert(await page.locator('.forms-resource').evaluate(el => Math.abs(el.getBoundingClientRect().width - el.parentElement.getBoundingClientRect().width) <= 1), 'Download card fills its grid row');
        }
        for (const deck of await page.locator('.public-swipe-carousel.is-ready').all()) {
          checks.push({width,path,...await inspectDeck(deck)});
        }
        assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));
        if ([1440,390].includes(width)) {
          await page.evaluate(()=>{document.activeElement?.blur();scrollTo(0,0);});
          await page.screenshot({path:`${output}/${path.split('/')[1] || 'home'}-${width}.png`,fullPage:true});
        }
      }
      console.log(`All cards readable at ${width}px`);
    }
    assert(checks.some(check=> new Set(check.widths).size > 1), 'Content must influence card widths');
    await page.setViewportSize({width:390,height:844});
    await page.goto(origin+'/resources/');
    await page.locator('.display-trigger').click();
    await page.locator('[data-preference=text]').selectOption('largest');
    await page.locator('.display-close').click();
    await page.evaluate(()=>new Promise(requestAnimationFrame));
    for (const deck of await page.locator('.public-swipe-carousel.is-ready').all()) await inspectDeck(deck);
    await page.evaluate(()=>document.documentElement.style.fontSize='200%');
    await page.waitForFunction(()=>document.querySelector('.public-swipe-viewport').clientHeight>320);
    for (const deck of await page.locator('.public-swipe-carousel.is-ready').all()) await inspectDeck(deck);
    await page.emulateMedia({media:'print'});
    assert.equal(await page.locator('.public-swipe-card:visible').count(),await page.locator('.public-swipe-card').count());
    const plain = await browser.newPage({javaScriptEnabled:false,viewport:{width:390,height:844}});
    await plain.goto(origin+'/resources/');
    assert.equal(await plain.locator('.public-swipe-card:visible').count(),await plain.locator('.public-swipe-card').count());
    await plain.close();
    const phone = await browser.newPage({viewport:{width:390,height:844},hasTouch:true,isMobile:true});
    await phone.goto(origin+'/about/');
    const deck = phone.locator('.public-swipe-carousel.is-ready');
    const viewport = deck.locator('.public-swipe-viewport');
    await viewport.scrollIntoViewIfNeeded();
    const first = await deck.locator('.public-swipe-count').textContent();
    const point = await viewport.evaluate(el=>{const r=el.getBoundingClientRect();return {x:r.x+r.width*.8,y:Math.max(100,Math.min(700,r.y+110))};});
    const cdp = await phone.context().newCDPSession(phone);
    await cdp.send('Input.dispatchTouchEvent',{type:'touchStart',touchPoints:[point]});
    for(let step=1;step<=6;step++) await cdp.send('Input.dispatchTouchEvent',{type:'touchMove',touchPoints:[{x:point.x-step*20,y:point.y}]});
    await cdp.send('Input.dispatchTouchEvent',{type:'touchEnd',touchPoints:[]});
    await phone.waitForFunction(first=>document.querySelector('.public-swipe-count').textContent!==first,first);
    assert.equal(await viewport.locator('.public-swipe-card:not([hidden])').evaluate(el=>el.scrollTop),0);
    await phone.close();
    assert.deepEqual(errors,[]);
    fs.writeFileSync(`${output}/results.json`,JSON.stringify({checks,errors,largeText:true,touch:true,print:true,noJavaScript:true,combinedBackgroundMission:true},null,2));
    console.log(`Passed ${checks.length} responsive deck checks, large text, touch, print and no-JavaScript fallback.`);
  } finally {await browser.close();}
})().catch(error=>{console.error(error);process.exitCode=1;});
