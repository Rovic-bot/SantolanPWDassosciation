const {chromium} = require(process.env.PLAYWRIGHT_MODULE || 'playwright');
const path = require('path');
const fs = require('fs');
const assert = require('assert/strict');

(async () => {
  const browser = await chromium.launch({headless:true,
    ...(process.env.CHROME_EXECUTABLE ? {executablePath:process.env.CHROME_EXECUTABLE} : {})});
  try {
    const context = await browser.newContext({viewport:{width:1440,height:1000}});
    const visitor = await browser.newContext({viewport:{width:1440,height:1000}});
    const page = await context.newPage();
    const publicPage = await visitor.newPage();
    const errors = [];
    for (const current of [page, publicPage]) {
      current.on('pageerror', error => errors.push(error.message));
      current.on('console', message => {if (message.type() === 'error') errors.push(message.text());});
      current.on('response', response => {if(response.status() >= 400) errors.push(`${response.status()} ${new URL(response.url()).pathname}`);});
    }
    const output = path.join(__dirname, '../.local/qa-gap002-20260930/browser');
    fs.mkdirSync(output, {recursive:true});
    const manage = `/events/manage/${process.env.QA_EVENT}/`;
    const roster = manage + 'attendance/';
    const go = async (route, current=page) => {
      const response = await current.goto(process.env.QA_URL + route, {waitUntil:'networkidle'});
      assert.equal(response.status(),200,route);
    };
    let responsiveChecks = 0;
    let enlargedTextChecks = 0;
    const responsive = async (current, name) => {
      for(const width of [320,390,768,1024,1440]) {
        await current.setViewportSize({width,height:1000});
        assert.equal(await current.evaluate(()=>document.documentElement.scrollWidth > innerWidth+1),false,`${name} overflow at ${width}`);
        assert.deepEqual(await current.evaluate(()=>{
          const ids = [...document.querySelectorAll('[id]')].map(element=>element.id);
          return ids.filter((id,index)=>ids.indexOf(id)!==index);
        }),[],`${name} duplicate IDs`);
        responsiveChecks++;
      }
      await current.screenshot({path:path.join(output,name+'-desktop.png'),fullPage:true});
      await current.setViewportSize({width:390,height:844});
      await current.locator('.display-trigger').click();
      await current.locator('#display-size').selectOption('largest');
      await current.locator('.display-close').click();
      assert.equal(await current.evaluate(()=>document.documentElement.scrollWidth > innerWidth+1),false,`${name} largest text overflow`);
      enlargedTextChecks++;
      await current.screenshot({path:path.join(output,name+'-mobile-largest.png'),fullPage:true});
      await current.locator('.display-trigger').click();
      await current.locator('#display-size').selectOption('default');
      await current.locator('.display-close').click();
      await current.setViewportSize({width:1440,height:1000});
    };
    await go(`/events/${process.env.QA_EVENT}/`, publicPage);
    await publicPage.getByText('Open to everyone', {exact:true}).waitFor();
    assert.equal(await publicPage.locator('main form').count(),0);
    await responsive(publicPage,'public-event');
    await go(roster,publicPage);
    assert.match(publicPage.url(),/accounts\/login\/\?next=/);
    await go('/accounts/login/');
    await page.getByLabel('Username:',{exact:true}).fill(process.env.QA_USERNAME);
    await page.getByLabel('Password:',{exact:true}).fill(process.env.QA_PASSWORD);
    await page.getByRole('button',{name:'Sign in',exact:true}).click();
    await page.waitForURL('**/dashboard/');
    await go(manage);
    await page.getByRole('link',{name:'Open event attendance',exact:false}).click();
    await page.waitForURL('**/attendance/');
    await page.getByRole('link',{name:'Record attendee',exact:true}).click();
    await page.waitForURL('**/attendance/new/');
    await responsive(page,'record-attendee');
    await page.getByLabel('Attendee name',{exact:false}).fill('Synthetic nonmember visitor');
    await page.getByLabel('Reason / attendance notes',{exact:false}).fill('Present at the venue.');
    await page.getByRole('button',{name:'Save attendee',exact:true}).click();
    await page.waitForURL(url=>/attendance\/[0-9a-f-]+\/$/.test(url.pathname));
    await responsive(page,'attendance-record');
    await page.getByLabel('Status',{exact:false}).selectOption('absent');
    await page.getByLabel('Reason / attendance notes',{exact:false}).fill('Corrected mistaken attendance.');
    await page.getByRole('button',{name:'Save attendance correction',exact:true}).click();
    await page.getByText('Corrected mistaken attendance.',{exact:true}).waitFor();
    await page.getByText('Before:',{exact:true}).first().waitFor();
    await responsive(page,'corrected-attendance');
    await go(roster+'new/');
    await page.getByLabel('Attendee name',{exact:false}).fill('Synthetic linked visitor');
    await page.getByLabel('Existing member',{exact:false}).selectOption(process.env.QA_MEMBER);
    await page.getByLabel('Reason / attendance notes',{exact:false}).fill('Member attended as an open participant.');
    await page.getByRole('button',{name:'Save attendee',exact:true}).click();
    await page.waitForURL(url=>/attendance\/[0-9a-f-]+\/$/.test(url.pathname));
    await page.getByRole('link',{name:'View linked member',exact:true}).click();
    await page.waitForURL('**/members/*/');
    await page.getByRole('heading',{name:'Open event attendance',exact:true}).waitFor();
    await responsive(page,'member-attendance-history');
    await go(roster);
    await responsive(page,'attendance-roster');
    await page.getByLabel('Attendee name',{exact:true}).fill('nonmember');
    await page.getByLabel('Status',{exact:true}).selectOption('absent');
    await page.getByRole('button',{name:'Filter attendance',exact:true}).click();
    await page.waitForURL('**/attendance/?*');
    await page.getByRole('rowheader',{name:'Synthetic nonmember visitor',exact:true}).waitFor();
    assert.equal(await page.getByRole('rowheader',{name:'Synthetic linked visitor',exact:true}).count(),0);
    await go(`/events/${process.env.QA_EVENT}/`,publicPage);
    assert.equal(await publicPage.getByText('Synthetic nonmember visitor',{exact:true}).count(),0);
    assert.equal(await publicPage.getByText('Synthetic linked visitor',{exact:true}).count(),0);
    assert.deepEqual(errors,[]);
    const result={status:'pass',actor:'ordinary authorized staff',responsiveChecks,enlargedTextChecks,browserErrors:errors,
      checks:['public open event','anonymous access denied','nonmember intake','reasoned correction and history',
        'inactive archived member link','member attendance history','filtered roster','legacy preservation','private attendee names'],screenshots:output};
    fs.writeFileSync(path.join(output,'results.json'),JSON.stringify(result,null,2));
    console.log(JSON.stringify(result));
  } finally {await browser.close();}
})().catch(error=>{console.error(error);process.exit(1);});
