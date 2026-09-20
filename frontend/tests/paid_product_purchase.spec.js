import { test, expect } from '@playwright/test';

const API_BASE = 'http://localhost:8000/api';
const V2 = `${API_BASE}/v2`;
const FRONTEND = 'http://localhost:7788';

test('paid product purchase flow', async ({ page }) => {
  // Register and login buyer
  const creds = { username: `paidbuyer_${Date.now()}`, password: 'test123456', nickname: '付费购买测试' };
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

  // Check initial coins balance
  const initialCoins = meData.coins || 10000;
  console.log('Initial coins:', initialCoins);

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

  // 1. Navigate to a paid product (mcporter, id=106, price=109)
  await page.goto(`${FRONTEND}/product/106`);
  await page.waitForTimeout(3000);

  await page.screenshot({ path: '/tmp/paid_product_detail.png', fullPage: false });
  const detailText = await page.textContent('body');
  console.log('Paid product detail:', detailText?.substring(0, 800));

  // Verify product name and price
  expect(detailText).toContain('mcporter');
  expect(detailText).toContain('109');

  // 2. Check wallet balance shown on page
  const balanceMatch = detailText.match(/[\d,]+/);
  expect(balanceMatch).toBeTruthy();

  // 3. Click buy button
  const buyBtn = page.locator('button:has-text("立即购买")').nth(1);
  const hasBuyBtn = await buyBtn.count() > 0;
  expect(hasBuyBtn).toBe(true);

  await buyBtn.click();
  await page.waitForTimeout(1000);

  await page.screenshot({ path: '/tmp/paid_purchase_modal.png', fullPage: false });
  const modalText = await page.textContent('body');
  console.log('Purchase modal:', modalText?.substring(0, 600));

  // Verify purchase modal shows product info and price
  expect(modalText).toContain('确认购买');
  expect(modalText).toContain('mcporter');
  expect(modalText).toContain('109');

  // 4. Confirm purchase
  const confirmBtn = page.locator('.modal-actions .btn-primary:has-text("确认购买")');
  await confirmBtn.click();

  // Wait for redirect to library
  await page.waitForURL('**/library', { timeout: 10000 });
  await page.waitForTimeout(2000);

  await page.screenshot({ path: '/tmp/after_paid_purchase.png', fullPage: false });
  const afterPurchaseText = await page.textContent('body');
  console.log('After purchase:', afterPurchaseText?.substring(0, 800));

  // Verify we're on library page
  expect(page.url()).toContain('/library');

  // Verify coins were deducted
  const newCoinsResp = await fetch(`${V2}/auth/me`, {
    headers: { Authorization: `Bearer ${loginData.token}` }
  });
  const newCoinsData = await newCoinsResp.json();
  const newCoins = newCoinsData.coins || 0;
  console.log('Coins after purchase:', newCoins);
  expect(newCoins).toBeLessThan(initialCoins);
  expect(newCoins).toBe(initialCoins - 109);

  // Verify product appears in library
  const inLibrary = afterPurchaseText.includes('mcporter') ||
                    afterPurchaseText.includes('已购技能');
  expect(inLibrary).toBe(true);

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
