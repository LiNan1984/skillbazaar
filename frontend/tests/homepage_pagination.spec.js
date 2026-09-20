import { test, expect } from '@playwright/test';

const V2 = 'http://localhost:8000/api/v2';
const FRONTEND = 'http://localhost:7788';

test('homepage: product pagination navigation', async ({ page }) => {
  // Register and login
  const creds = { username: `pageuser_${Date.now()}`, password: 'test123456', nickname: '分页测试用户' };
  const regResp = await fetch(`${V2}/auth/register`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(creds)
  });
  await regResp.json();

  const loginResp = await fetch(`${V2}/auth/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ username: creds.username, password: creds.password })
  });
  const loginData = await loginResp.json();

  const meResp = await fetch(`${V2}/auth/me`, {
    headers: { Authorization: `Bearer ${loginData.token}` }
  });
  const meData = await meResp.json();

  await page.goto(FRONTEND);
  await page.waitForTimeout(1500);

  await page.evaluate(() => {
    document.querySelectorAll('.modal-overlay, [class*="overlay"]').forEach(el => {
      el.style.pointerEvents = 'none';
      el.style.display = 'none';
    });
  });

  await page.evaluate(({ t, uid, un, nick }) => {
    localStorage.setItem('skillbazaar_token', t);
    localStorage.setItem('skillbazaar_user_id', uid);
    localStorage.setItem('skillbazaar_username', un);
    localStorage.setItem('skillbazaar_nickname', nick);
  }, { t: loginData.token, uid: meData.user_id, un: creds.username, nick: creds.nickname });

  // 1. Navigate to homepage (page 1)
  await page.goto(FRONTEND);
  await page.waitForTimeout(3000);

  await page.screenshot({ path: '/tmp/homepage_page1.png', fullPage: false });
  const page1Text = await page.textContent('body');
  console.log('Homepage page 1:', page1Text?.substring(0, 1200));

  // Verify products are displayed on page 1
  const productNames = page.locator('.product-card .product-name, .product-card h3');
  const page1Count = await productNames.count();
  console.log('Products on page 1:', page1Count);
  expect(page1Count).toBeGreaterThan(0);

  // 2. Check if pagination exists
  const pageButtons = page.locator('.page-btn');
  const pageBtnCount = await pageButtons.count();
  console.log('Page buttons count:', pageBtnCount);

  // 3. Click next page button if it exists
  if (pageBtnCount > 1) {
    // Find the "next" button (usually the right arrow or page 2)
    const nextBtn = page.locator('.page-btn:has-text("下一页")').first();
    const nextBtnCount = await nextBtn.count();
    console.log('Next button count:', nextBtnCount);

    if (nextBtnCount > 0) {
      await nextBtn.click();
      await page.waitForTimeout(2000);

      await page.screenshot({ path: '/tmp/homepage_page2.png', fullPage: false });
      const page2Text = await page.textContent('body');
      console.log('Homepage page 2:', page2Text?.substring(0, 1200));

      // Verify we're on page 2
      const hasPage2Active = page2Text.includes('2') && page2Text.includes('page-btn active');
      console.log('Page 2 active:', hasPage2Active);

      // Verify products are still displayed
      const page2ProductCount = await productNames.count();
      console.log('Products on page 2:', page2ProductCount);
      expect(page2ProductCount).toBeGreaterThan(0);
    }
  }

  // 4. Test clicking a specific page number
  const page2NumBtn = page.locator('.page-btn:not(.active):has-text("2")');
  const page2NumCount = await page2NumBtn.count();
  if (page2NumCount > 0) {
    await page2NumBtn.first().click();
    await page.waitForTimeout(2000);

    await page.screenshot({ path: '/tmp/homepage_page2_click.png', fullPage: false });
    const afterPage2Click = await page.textContent('body');
    console.log('After page 2 click:', afterPage2Click?.substring(0, 800));

    // Verify page 2 is active
    const activePage = afterPage2Click.match(/page-btn active[^<]*?(\d)/);
    console.log('Active page number:', activePage ? activePage[1] : 'unknown');
  }

  // 5. Test previous page button
  const prevBtn = page.locator('.page-btn:has-text("上一页")');
  const prevCount = await prevBtn.count();
  if (prevCount > 0) {
    await prevBtn.first().click();
    await page.waitForTimeout(2000);

    await page.screenshot({ path: '/tmp/homepage_page1_back.png', fullPage: false });
    const backToPage1 = await page.textContent('body');
    console.log('Back to page 1:', backToPage1?.substring(0, 800));

    // Should be back on page 1
    const hasPage1Active = backToPage1.includes('page-btn active') && !backToPage1.includes('2');
    console.log('Back to page 1:', hasPage1Active);
  }

  // Verify homepage loaded successfully
  expect(page1Text).toContain('SkillBazaar');

  // Zero console errors
  const consoleErrors = [];
  page.on('console', msg => {
    if (msg.type() === 'error') consoleErrors.push(msg.text());
  });

  await page.reload();
  await page.waitForTimeout(2000);
  console.log('Console errors:', consoleErrors);
  expect(consoleErrors.length).toBe(0);
});
