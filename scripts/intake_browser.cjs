const fs = require('fs'), path = require('path'), assert = require('assert/strict');
const {chromium} = require(process.env.PLAYWRIGHT_MODULE || path.join(process.env.USERPROFILE,
    '.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright'));
const input = JSON.parse(fs.readFileSync(process.env.INTAKE_BROWSER_INPUT || process.argv[2], 'utf8'));
if(input.login_file) input.login=JSON.parse(fs.readFileSync(input.login_file,'utf8'));
const output = input.output; fs.mkdirSync(output, {recursive:true});
let currentPage;
(async () => {
    const browser = await chromium.launch({headless:true, executablePath:process.env.CHROME_EXECUTABLE || 'C:/Program Files/Google/Chrome/Application/chrome.exe'});
    const result = {actions:[], responsive:[], errors:[]};
    try {
        const admin = await browser.newContext({viewport:{width:1440,height:1000}, reducedMotion:'reduce'});
        if(input.cookie) await admin.addCookies([{name:input.cookie.name,value:input.cookie.value,url:input.url}]);
        const page = await admin.newPage(); page.setDefaultTimeout(90000);
        currentPage=page;
        page.on('pageerror', e => result.errors.push(e.message));
        const go = async (page, route) => {
            const response = await page.goto(input.url + route, {waitUntil:'networkidle'});
            assert.equal(response.status(), 200, route);
        };
        const post = async (page, button) => {
            const form=await button.locator('xpath=ancestor::form[1]').elementHandle();
            const ajax=form && await form.evaluate(node=>node.hasAttribute('data-applicant-review-form'));
            const [response] = await Promise.all([page.waitForResponse(r=>r.request().method()==='POST'),button.click()]);
            if(![200,302].includes(response.status())) assert.fail(await response.text());
            if(ajax) await page.waitForFunction(node=>!node.isConnected || node.dataset.saving!=='true',form);
            await page.waitForLoadState('networkidle');
            const errors = await page.locator('.errorlist').allTextContents();
            assert.ok(!errors.some(text=>text.trim()), errors.join('\n'));
            const failures=await page.locator('.alert-danger').allTextContents();
            assert.ok(!failures.some(text=>text.trim()),failures.join('\n'));
            if(response.status()===200 && !response.url().endsWith('/access/') && !ajax) {
                assert.fail(await page.locator('main').innerText());
            }
            const inline=await page.locator('[data-review-error]:visible, form p.text-danger').allTextContents();
            assert.ok(!inline.some(text=>text.trim()),inline.join('\n'));
        };
        if(input.login) {
            await go(page,'/accounts/login/');
            await page.locator('[name=username]').fill(input.login.username);
            await page.locator('[name=password]').fill(input.login.password);
            await post(page,page.getByRole('button',{name:'Sign in',exact:true}));
        }
        if(input.phase === 'matching-check') {
            await go(page,`/programs/manage/${input.rankingProgram}/`);
            await page.screenshot({path:path.join(output,'24-repaired-program-history.png'),fullPage:false});
            for(const program of input.programs) {
                const response=await admin.request.get(input.url+`/programs/manage/${program}/`);
                assert.equal(response.status(),200,'Program detail '+program);
            }
            const publicContext=await browser.newContext({viewport:{width:1440,height:1000}});
            const visitor=await publicContext.newPage(); currentPage=visitor;
            visitor.on('pageerror',e=>result.errors.push(e.message));
            await go(visitor,`/programs/${input.program}/verify/`);
            assert.equal(await visitor.locator('[name=application_code]').count(),0);
            assert.equal(await visitor.locator('[name=disability_types]').count(),10);
            await visitor.screenshot({path:path.join(output,'21-member-matching-form.png'),fullPage:true});
            for(const width of [320,390,768,1440]) {
                await visitor.setViewportSize({width,height:1000});
                assert.equal(await visitor.evaluate(()=>document.documentElement.scrollWidth>innerWidth+1),false);
                if(width===390) await visitor.screenshot({path:path.join(output,'22-member-matching-mobile.png'),fullPage:true});
            }
            await visitor.locator('[name=control_number]').fill(input.member.control_number);
            await visitor.locator('[name=full_name]').fill(input.member.full_name);
            for(const id of input.member.disability_types) await visitor.locator(`[name=disability_types][value="${id}"]`).check();
            await visitor.locator('[name=disability_cause]').selectOption(input.member.cause);
            await visitor.locator('[name=disability_visibility]').selectOption(input.member.visibility);
            const failure="We couldn't match your information with the Association's membership records or this program's qualifications. Please check your details or contact the Association Help Desk.";
            for(const field of ['control_number','full_name']) {
                await visitor.locator(`[name=${field}]`).fill('NOT A MATCH');
                const [response]=await Promise.all([visitor.waitForResponse(r=>r.request().method()==='POST'),
                    visitor.getByRole('button',{name:'Verify & Continue',exact:true}).click()]);
                assert.equal(response.status(),200);
                await visitor.waitForLoadState('networkidle');
                assert.equal(await visitor.locator('.errorlist.nonfield').innerText(),failure);
                assert.ok(visitor.url().endsWith('/verify/'));
                await visitor.locator(`[name=${field}]`).fill(input.member[field]);
            }
            await post(visitor,visitor.getByRole('button',{name:'Verify & Continue',exact:true}));
            assert.ok(visitor.url().endsWith('/apply/'));
            assert.equal(await visitor.locator(`[name=requirement_${input.requirement}]`).count(),1);
            await visitor.screenshot({path:path.join(output,'23-matched-program-requirements.png'),fullPage:true});
            assert.deepEqual(result.errors,[]);
            fs.writeFileSync(path.join(output,'member-matching-browser-results.json'),JSON.stringify({passed:true,
                program_pages:input.programs.length,responsive_checks:4,invalid_control:true,invalid_name:true,
                valid_match_to_uploads:true,no_application_submitted:true},null,2));
            console.log('Membership matching browser checks passed; '+input.programs.length+' program pages returned 200; no application submitted.');
            await publicContext.close();
            return;
        }
        if(input.phase === 'screenshots') {
            await go(page,`/programs/${input.program}/verify/`);
            await page.screenshot({path:path.join(output,'14-public-application.png'),fullPage:true});
            await page.setViewportSize({width:390,height:1000});
            await page.screenshot({path:path.join(output,'15-public-mobile.png'),fullPage:true});
            await page.setViewportSize({width:1440,height:1000});
            await go(page,`/programs/manage/${input.program}/applications/${input.application}/`);
            await page.screenshot({path:path.join(output,'17-admin-eligibility.png'),fullPage:false});
            await go(page,`/manage/program-intake/${input.application}/sources/`);
            await page.screenshot({path:path.join(output,'18-verified-ewaf-sources.png'),fullPage:true});
            await go(page,`/ewaf/programs/${input.rankingProgram}/`);
            await page.locator('#results').scrollIntoViewIfNeeded();
            await page.screenshot({path:path.join(output,'20-employment-ranking.png'),fullPage:false});
            assert.deepEqual(result.errors,[]);
            console.log('Refreshed five screenshots using read-only page visits.');
            return;
        }
        if(input.phase !== 'ranking') {
            const publicContext = await browser.newContext({viewport:{width:1440,height:1000}});
            const visitor = await publicContext.newPage(); visitor.setDefaultTimeout(90000);
            visitor.on('pageerror',e=>result.errors.push(e.message));
            await go(visitor,`/programs/${input.program}/verify/`);
            assert.equal(await visitor.locator('[name=disability_types]').count(),10);
            assert.equal(await visitor.locator('[name=application_code]').count(),0);
            await visitor.screenshot({path:path.join(output,'14-public-application.png'),fullPage:true});
            for(const width of [320,390,768,1440]) {
                await visitor.setViewportSize({width,height:1000});
                assert.equal(await visitor.evaluate(()=>document.documentElement.scrollWidth>innerWidth+1),false,'Public overflow at '+width);
                result.responsive.push({surface:'public application',width});
                if(width===390) await visitor.screenshot({path:path.join(output,'15-public-mobile.png'),fullPage:true});
            }
            await visitor.locator('[name=control_number]').fill(input.member.control_number);
            await visitor.locator('[name=full_name]').fill(input.member.full_name || input.member.name);
            for(const id of input.member.disability_types) await visitor.locator(`[name=disability_types][value="${id}"]`).check();
            await visitor.locator('[name=disability_cause]').selectOption(input.member.cause);
            await visitor.locator('[name=disability_visibility]').selectOption(input.member.visibility);
            await post(visitor,visitor.getByRole('button',{name:'Verify & Continue',exact:true}));
            if(visitor.url().includes('/apply/')) {
                await visitor.screenshot({path:path.join(output,'16-program-uploads.png'),fullPage:true});
                await visitor.locator('[name=calendar_photo]').setInputFiles(input.photo);
                await visitor.locator(`[name=requirement_${input.requirement}]`).setInputFiles(input.document);
                await post(visitor,visitor.getByRole('button',{name:'Submit application',exact:true}));
            }
            assert.ok(visitor.url().includes('/submitted/'));
            result.actions.push('Onsite control number, full name and disability match → dynamic upload → real pending application');
            await go(page,`/programs/manage/${input.program}/applications/`);
            const link = page.locator(`a[href*="/programs/manage/${input.program}/applications/"]`).filter({hasText:input.member.name}).first();
            await link.click(); await page.waitForLoadState('networkidle');
            const application = page.url().match(/applications\/([^/]+)\//)[1]; result.application=application;
            const identity = page.locator('#photo-review');
            if(!(await identity.evaluate(node=>node.open))) await identity.locator('summary').click();
            if(await identity.getByRole('button',{name:'Verify Identity',exact:true}).count()) {
                await identity.locator('[name=reason]').fill('Fictional browser test: current synthetic portrait matches the onsite fictional member.');
                await identity.locator('[name=confirm]').check();
                await post(page,identity.getByRole('button',{name:'Verify Identity',exact:true}));
            }
            await page.locator('a.review-check[data-review-target=documents]').click();
            const required = page.locator(`[name=check_${input.requirement}][value=pass]`);
            if(await required.count()) await required.check();
            else await page.locator(`[name=check_${input.requirement}]`).selectOption('pass');
            const instructions = page.locator('[name=other_requirements][value=pass]');
            if(await instructions.count()) await instructions.check();
            else await page.locator('[name=other_requirements]').selectOption('pass');
            await page.locator('#eligibility-decision-form [name=notes]').fill('Fictional browser test: required evidence reviewed; optional evidence is not supplied and is not required.');
            await post(page,page.getByRole('button',{name:'Mark Eligible',exact:true}));
            await page.screenshot({path:path.join(output,'17-admin-eligibility.png'),fullPage:false});
            await go(page,`/manage/program-intake/${application}/sources/`);
            const review = page.locator('form').filter({has:page.locator('[name=action][value=review]')});
            await review.locator('[name=value]').fill('90');
            await review.locator('[name=reason]').fill('Fictional browser test: read the submitted document and verified its observed measurement of 90 assessment units.');
            await review.locator('[name=confirmed]').check();
            await post(page,review.getByRole('button',{name:'Save evidence review',exact:true}));
            const collect = page.locator('form').filter({has:page.locator('[name=action][value=collect]')});
            await collect.locator('[name=reason]').fill('Fictional browser test: verified the displayed onsite employment and dependents; PA comes from actual confirmed non-voided receipts.');
            await collect.locator('[name=confirmed]').check();
            await post(page,collect.getByRole('button',{name:'Collect SI, ES, PA and ND',exact:true}));
            assert.ok((await page.locator('main').innerText()).includes('SI: 90'));
            await page.screenshot({path:path.join(output,'18-verified-ewaf-sources.png'),fullPage:true});
            for(const width of [390,768,1440]) {
                await page.setViewportSize({width,height:1000});
                assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth+1),false,'Admin source overflow at '+width);
                result.responsive.push({surface:'Admin sources',width});
            }
            result.actions.push('Admin identity and checklist review → Eligible → SI document verification → four source assessments');
            await publicContext.close();
        }
        if(input.rankingProgram) {
            result.rankings={};
            result.leaders={};
            await page.setViewportSize({width:1440,height:1000});
            for(const code of ['SI','ES']) {
                await go(page,`/ewaf/programs/${input.rankingProgram}/`);
                const names={SI:'Socioeconomic Indicator',ES:'Employment Status'};
                while((await page.locator('.weight-row').first().getAttribute('data-criterion'))!==code) {
                    await page.getByRole('button',{name:`Move ${names[code]} higher in priority`,exact:true}).click();
                }
                await page.locator('#weight-'+code).evaluate(input=>{
                    input.value='7000'; input.dispatchEvent(new Event('input',{bubbles:true})); input.dispatchEvent(new Event('change',{bubbles:true}));
                });
                assert.equal(await page.locator('#weight-total').innerText(),'100.00%');
                await page.getByRole('button',{name:'Review AHP result',exact:true}).click();
                await page.locator('#weight-preview').waitFor({state:'visible'});
                await page.locator('[name=accept_derived_weights]').check();
                await page.locator('#configuration [name=reason]').fill('Fictional browser experiment: review AHP-derived '+code+' emphasis and preserve prior results.');
                await page.locator('[name=attested]').check();
                await post(page,page.getByRole('button',{name:'Lock configuration',exact:true}));
                const generate=page.locator('#calculate form');
                await generate.locator('[name=reason]').fill('Fictional browser experiment: calculate the complete verified source pool.');
                await post(page,generate.getByRole('button',{name:'Generate EWAF',exact:true}));
                await page.locator('#results').scrollIntoViewIfNeeded();
                result.rankings[code]=await page.locator('#results table tbody tr').allTextContents();
                result.leaders[code]=await page.locator('#results table tbody tr').first().locator('th a').innerText();
                await page.screenshot({path:path.join(output,code==='SI'?'19-si-ranking.png':'20-employment-ranking.png'),fullPage:false});
            }
            assert.notEqual(result.leaders.SI,result.leaders.ES);
            result.actions.push('Slider priority → 100% proposal → AHP review → configuration authorization → real recalculation and changed first applicant');
        }
        assert.deepEqual(result.errors,[]);
        fs.writeFileSync(path.join(output,'intake-browser-results.json'),JSON.stringify(result,null,2));
        console.log(JSON.stringify({passed:true,actions:result.actions,responsive:result.responsive.length,application:result.application}));
    } catch(error) {
        if(currentPage) {
            await currentPage.screenshot({path:path.join(output,'intake-browser-failure.png'),fullPage:true});
            fs.writeFileSync(path.join(output,'intake-browser-failure.txt'),await currentPage.locator('main').innerText());
        }
        throw error;
    } finally { await browser.close(); }
})().catch(error=>{console.error(error);process.exit(1);});
