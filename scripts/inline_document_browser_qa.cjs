const assert=require('assert/strict'), path=require('path');
const {chromium}=require(process.env.PLAYWRIGHT_MODULE || path.join(process.env.USERPROFILE,
    '.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright'));
(async()=>{
    const browser=await chromium.launch({headless:true,executablePath:process.env.CHROME_EXECUTABLE});
    try {
        const context=await browser.newContext({viewport:{width:1440,height:1050},reducedMotion:'reduce',permissions:['clipboard-read','clipboard-write']});
        await context.addCookies([{name:process.env.QA_COOKIE_NAME,value:process.env.QA_SESSION,url:process.env.QA_URL}]);
        const page=await context.newPage(), errors=[];
        page.on('pageerror',e=>errors.push(e.message));
        page.on('dialog',async dialog=>{errors.push('Unexpected popup: '+dialog.type());await dialog.dismiss();});
        page.on('popup',()=>errors.push('Unexpected new page'));
        page.on('response',r=>{if(r.status()>=500)errors.push(r.url());});
        const url=process.env.QA_URL+process.env.QA_APPLICATION+'#documents';
        assert.equal((await page.goto(url,{waitUntil:'networkidle'})).status(),200);
        let navigations=0;
        page.on('framenavigated',frame=>{if(frame===page.mainFrame())navigations++;});
        const button=page.locator('#review-document-'+process.env.QA_DOCUMENT);
        const expiredButton=page.locator('#review-document-'+process.env.QA_EXPIRED_DOCUMENT);
        assert.equal(await page.getByRole('link',{name:'Review document',exact:true}).count(),0);
        assert.equal(await page.locator('dialog[id^="document-dialog-"]').count(),0);
        assert.equal(await button.innerText(),'Needs Review');
        const save=async(action)=>{
            const [response]=await Promise.all([
                page.waitForResponse(r=>r.request().method()==='POST' && new URL(r.url()).pathname===process.env.QA_APPLICATION),
                action()
            ]);
            assert.equal(response.status(),200);
            await page.waitForLoadState('networkidle');
        };
        await page.screenshot({path:path.join(process.env.QA_OUTPUT,'document-needs-review.png')});
        await button.focus();
        await save(()=>page.keyboard.press('Enter'));
        await page.waitForFunction(id=>document.getElementById(id).textContent==='Review','review-document-'+process.env.QA_DOCUMENT);
        assert.equal(await button.innerText(),'Review');
        assert.equal(await button.isDisabled(),true);
        assert.equal(await page.locator('dialog[open]').count(),0);
        assert.equal(page.url(),url);
        assert.equal(navigations,0);
        assert.equal(await page.locator('#document-review-status').innerText(),'Document review saved.');
        // Other applicant controls remain functional after the in-place refresh.
        await page.getByRole('button',{name:'Copy control number',exact:true}).click();
        await page.waitForFunction(()=>document.getElementById('member-copy-status').textContent==='Control number copied.');
        await page.locator('#documents').scrollIntoViewIfNeeded();
        await page.screenshot({path:path.join(process.env.QA_OUTPUT,'document-review-saved.png')});
        await save(()=>expiredButton.click());
        const expiredCard=page.locator('[data-member-document="'+process.env.QA_EXPIRED_DOCUMENT+'"]');
        await expiredCard.getByRole('alert').filter({hasText:'An expired document cannot be marked current and verified.'}).waitFor();
        assert.equal(await expiredButton.innerText(),'Needs Review');
        assert.equal(await expiredButton.isDisabled(),false);
        assert.equal(await page.locator('dialog[open]').count(),0);
        assert.equal(page.url(),url);
        assert.equal(navigations,0);
        for(const width of [320,390,768,1440]) {
            await page.setViewportSize({width,height:1050});
            await button.scrollIntoViewIfNeeded();
            assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth+1),false,`Overflow at ${width}`);
            const box=await button.boundingBox();
            assert.ok(box.x>=0 && box.x+box.width<=width+1);
            if(width===390)await page.screenshot({path:path.join(process.env.QA_OUTPUT,'document-review-mobile.png')});
        }
        await page.reload({waitUntil:'networkidle'});
        assert.equal(await button.innerText(),'Review');
        assert.deepEqual(errors,[]);
        console.log('PASS: one-click document review, persisted Review/Needs Review states, expiry validation, no popup or navigation, keyboard and copy controls, four responsive widths.');
    } finally {await browser.close();}
})().catch(error=>{console.error(error);process.exitCode=1;});
