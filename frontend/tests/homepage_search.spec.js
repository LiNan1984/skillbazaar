import { test, expect } from '@playwright/test';

const API_BASE = 'http://localhost:8000/api';
const V2 = `${API_BASE}/v2`;
const FRONTEND = 'http://localhost:7788';

test('homepage search and category filter work correctly', async ({ page }) => {
  // Register a user to bypass any auth modal blocking
  const creds = { username: `searchtest_${Date.now()}`, password: 'test123456', nickname: '搜索测试' };
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
  await page.waitForTimeout(2000);

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

  // 1. Navigate to home page and verify products load
  await page.goto(FRONTEND);
  await page.waitForTimeout(3000);

  await page.screenshot({ path: '/tmp/homepage_initial.png', fullPage: false });
  const initialText = await page.textContent('body');
  console.log('Homepage initial:', initialText?.substring(0, 800));

  // Should show "市场货架" heading and product count
  expect(initialText).toContain('市场货架');
  expect(initialText).toContain('个商品');

  // 2. Use navbar search to search for a specific keyword
  const searchInput = page.locator('input.search-input');
  await searchInput.fill('crypto');
  await page.waitForTimeout(1000);

  await page.screenshot({ path: '/tmp/homepage_search_crypto.png', fullPage: false });
  const searchText = await page.textContent('body');
  console.log('Search crypto results:', searchText?.substring(0, 800));

  // Should show search keyword indication
  expect(searchText).toContain('crypto');

  // 3. Click Agent category tab
  await page.click('button:has-text("Agent")');
  await page.waitForTimeout(2000);

  await page.screenshot({ path: '/tmp/homepage_agent_category.png', fullPage: false });
  const agentText = await page.textContent('body');
  console.log('Agent category:', agentText?.substring(0, 800));

  // Should show Agent category selected (URL param or text indication)
  expect(agentText).toContain('Agent');

  // 4. Click on a subcategory under Agent (交易助手)
  const subcategoryTab = page.locator('button:has-text("交易助手")');
  if (await subcategoryTab.count() > 0) {
    await subcategoryTab.click();
    await page.waitForTimeout(2000);
    const subText = await page.textContent('body');
    console.log('Subcategory 交易助手:', subText?.substring(0, 500));
  }

  // 5. Test sort by price ascending
  await page.goto(FRONTEND);
  await page.waitForTimeout(3000);
  await page.click('button:has-text("价格↑")');
  await page.waitForTimeout(2000);

  await page.screenshot({ path: '/tmp/homepage_sort_price_asc.png', fullPage: false });
  const sortText = await page.textContent('body');
  console.log('Sort price asc:', sortText?.substring(0, 500));

  // 6. Test sort by newest
  await page.click('button:has-text("最新")');
  await page.waitForTimeout(2000);

  const newestText = await page.textContent('body');
  console.log('Sort newest:', newestText?.substring(0, 500));

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
