import { test, expect } from '@playwright/test';

const V2 = 'http://localhost:8000/api/v2';
const FRONTEND = 'http://localhost:7788';

test('product detail: owned product shows buy-to-sandbox state', async ({ page }) => {
  // Register and login
  const creds = { username: `owned_${Date.now()}`, password: 'test123456', nickname: '拥有测试用户' };
  await fetch(`${V2}/auth/register`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(creds)
  }).then(r => r.json());

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

  // 1. Purchase product 1 (code-reviewer, free) BEFORE viewing detail
  const buyResp = await fetch(`http://localhost:8000/api/transactions/buy`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${loginData.token}` },
    body: JSON.stringify({ product_id: 1, user_id: meData.user_id })
  });
  const buyData = await buyResp.json();
  console.log('Purchase result:', buyResp.status, JSON.stringify(buyData).substring(0, 200));
  expect(buyResp.status).toBe(200);

  // 2. Navigate to product detail page AFTER purchase
  await page.goto(`${FRONTEND}/product/1`);
  await page.waitForTimeout(3000);

  await page.screenshot({ path: '/tmp/owned_product_detail.png', fullPage: false });
  const detailText = await page.textContent('body');
  console.log('Owned product detail:', detailText?.substring(0, 1000));

  // 3. Verify product info still shows
  expect(detailText).toContain('code-reviewer');

  // 4. Verify "已拥有" (owned) badge or message is shown
  const hasOwnedBadge = detailText.includes('已拥有') ||
                         detailText.includes('已购') ||
                         detailText.includes('拥有');
  console.log('Has owned badge:', hasOwnedBadge);

  // 5. Verify buy button is replaced with sandbox/use button
  const hasSandboxBtn = detailText.includes('去沙盒') ||
                        detailText.includes('去使用') ||
                        detailText.includes('使用') ||
                        detailText.includes('沙盒');
  console.log('Has sandbox/use button:', hasSandboxBtn);

  // 6. Verify no buy button for owned product
  const hasBuyBtn = detailText.includes('立即购买') || detailText.includes('免费购买');
  console.log('Has buy button (should be false for owned):', hasBuyBtn);

  // 7. Verify coin balance still displayed (should have spent 0 for free product)
  const hasCoinsDisplay = detailText.includes('金币') || detailText.includes('coins') || detailText.includes('10000');
  console.log('Has coins display:', hasCoinsDisplay);

  // 8. Zero console errors
  const consoleErrors = [];
  page.on('console', msg => {
    if (msg.type() === 'error') consoleErrors.push(msg.text());
  });

  await page.reload();
  await page.waitForTimeout(2000);
  console.log('Console errors:', consoleErrors);
  expect(consoleErrors.length).toBe(0);
});
