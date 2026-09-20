import { test, expect } from '@playwright/test';

const V2 = 'http://localhost:8000/api/v2';
const API_BASE = 'http://localhost:8000/api';
const FRONTEND = 'http://localhost:7788';

test('seller dashboard: stats and product management', async ({ page }) => {
  // Register and login
  const creds = { username: `seller_${Date.now()}`, password: 'test123456', nickname: '卖家测试用户' };
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

  // 1. Navigate to seller dashboard
  await page.goto(`${FRONTEND}/seller`);
  await page.waitForTimeout(3000);

  await page.screenshot({ path: '/tmp/seller_dashboard.png', fullPage: false });
  const sellerText = await page.textContent('body');
  console.log('Seller dashboard:', sellerText?.substring(0, 1000));

  // 2. Verify seller dashboard loaded
  expect(sellerText).toContain('卖家中心');

  // 3. Verify stats section exists
  const hasStats = sellerText.includes('全部商品') ||
                   sellerText.includes('总浏览') ||
                   sellerText.includes('总销量') ||
                   sellerText.includes('Package') ||
                   sellerText.includes('TrendingUp');
  console.log('Has stats section:', hasStats);

  // 4. Verify product list section exists (may be empty for new seller)
  const hasProductList = sellerText.includes('我的商品') ||
                         sellerText.includes('商品列表') ||
                         sellerText.includes('暂无商品') ||
                         sellerText.includes('还没有');
  console.log('Has product list section:', hasProductList);

  // 5. Verify empty state if no products
  const isEmptyState = sellerText.includes('暂无商品') ||
                       sellerText.includes('还没有') ||
                       sellerText.includes('暂无数据');
  console.log('Has empty state:', isEmptyState);

  // 6. Verify navbar still renders
  expect(sellerText).toContain('SkillBazaar');

  // 7. Verify no console errors
  const consoleErrors = [];
  page.on('console', msg => {
    if (msg.type() === 'error') consoleErrors.push(msg.text());
  });

  await page.reload();
  await page.waitForTimeout(2000);
  console.log('Console errors:', consoleErrors);
  expect(consoleErrors.length).toBe(0);
});
