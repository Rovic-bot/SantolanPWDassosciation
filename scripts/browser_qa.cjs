// Optional Playwright harness; runs only against Django's disposable test server.
const { chromium } = require(process.env.PLAYWRIGHT_MODULE || 'playwright');
const path = require('path');
const fs = require('fs');
const assert = require('assert/strict');

(async () => {
  const browser = await chromium.launch({headless: true,
    ...(process.env.CHROME_EXECUTABLE ? {executablePath: process.env.CHROME_EXECUTABLE} : {})});
  try {
    const page = await browser.newPage({viewport: {width: 1440, height: 1000}});
    const errors = [];
    page.on('pageerror', error => errors.push(error.message));
    page.on('response', response => {if (response.status() >= 400) errors.push(`${response.status()} ${response.url()}`);});
    const output = path.join(__dirname, '../.local/qa-milestone20');
    fs.mkdirSync(output, {recursive: true});
    const go = async route => {
      const response = await page.goto(process.env.QA_URL + route, {waitUntil: 'networkidle'});
      assert.equal(response.status(), 200, route);
    };
    const screenshot = name => page.screenshot({path: path.join(output, name + '.png'), fullPage: true});
    const noOverflow = async () => assert.equal(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth), false, `Overflow at ${page.viewportSize().width}: ${page.url()}`);
    const routes = ['/', '/about/', '/announcements/', '/events/', '/programs/', '/membership/register/', '/contact/', '/accounts/login/'];
    for (const width of [320, 390, 768, 1024, 1440]) {
      await page.setViewportSize({width, height: 900});
      for (const route of routes) {
        await go(route);
        await noOverflow();
        assert.equal(await page.locator('h1').count(), 1);
        if (route !== '/accounts/login/') assert.equal(await page.getByRole('navigation', {name: 'Main navigation'}).locator('[aria-current="page"]').count(), 1);
      }
    }
    await screenshot('login-desktop');
    await go('/');
    await screenshot('home-desktop');
    await page.keyboard.press('Tab');
    assert.equal(await page.locator(':focus').textContent(), 'Skip to main content');
    await page.keyboard.press('Enter');
    assert.equal(await page.locator(':focus').getAttribute('id'), 'main-content');
    await page.setViewportSize({width: 390, height: 844});
    await go('/about/');
    const toggle = page.getByRole('button', {name: 'Toggle navigation'});
    await toggle.click();
    await page.locator('#public-nav.collapse.show').waitFor();
    assert.equal(await toggle.getAttribute('aria-expanded'), 'true');
    await page.getByRole('link', {name: 'Events', exact: true}).click();
    await page.waitForURL('**/events/');
    await screenshot('events-mobile');
    await go('/accounts/login/');
    await screenshot('login-mobile');
    await page.getByLabel('Username:', {exact: true}).fill(process.env.QA_USERNAME);
    await page.getByLabel('Password:', {exact: true}).fill(process.env.QA_PASSWORD);
    await page.getByRole('button', {name: 'Sign in', exact: true}).click();
    await page.waitForURL('**/dashboard/');
    await noOverflow();
    await screenshot('dashboard-mobile');
    await page.setViewportSize({width: 1440, height: 1000});
    await screenshot('dashboard-desktop');
    await page.getByRole('link', {name: 'Manage roles (groups)'}).click();
    await page.waitForURL('**/admin/auth/group/');
    await page.getByRole('link', {name: 'Add group'}).click();
    await page.getByLabel('Name:', {exact: true}).fill('Browser verification role');
    // Django's permission selector must offer the custom dashboard permission.
    const available = page.locator('#id_permissions_from');
    await available.selectOption({label: 'Accounts | administrator | Can access administration dashboard'});
    await page.locator('#id_permissions_add').click();
    await page.locator('input[name="_save"]').click();
    await page.waitForURL('**/admin/auth/group/');
    await page.locator('#result_list').getByRole('link', {name: 'Browser verification role', exact: true}).waitFor();
    await screenshot('roles-desktop');
    await go('/admin/audit/securityevent/');
    await page.getByRole('cell', {name: 'Signed in', exact: true}).first().waitFor();
    await go('/accounts/password/change/');
    await page.setViewportSize({width: 390, height: 844});
    await noOverflow();
    await screenshot('password-mobile');
    await page.getByLabel('Old password:', {exact: true}).fill(process.env.QA_PASSWORD);
    const newPassword = process.env.QA_PASSWORD + '-changed';
    await page.getByLabel('New password:', {exact: true}).fill(newPassword);
    await page.getByLabel('New password confirmation:', {exact: true}).fill(newPassword);
    await page.getByRole('button', {name: 'Save new password'}).click();
    await page.waitForURL('**/accounts/password/changed/');
    await page.getByRole('button', {name: 'Workspace menu'}).click();
    await page.getByRole('button', {name: 'Sign out', exact: true}).click();
    await page.waitForURL('**/accounts/login/');
    await go('/dashboard/');
    assert.match(page.url(), /accounts\/login\/\?next=/);
    assert.deepEqual(errors, []);
    console.log(JSON.stringify({status: 'pass', publicRoutes: 8, widths: [320,390,768,1024,1440],
      checks: ['keyboard skip link', 'mobile navigation', 'active navigation', 'login', 'role creation with permission', 'audit list', 'password change', 'logout', 'no page/resource errors'], screenshots: output}));
  } finally {
    await browser.close();
  }
})().catch(error => { console.error(error); process.exitCode = 1; });
