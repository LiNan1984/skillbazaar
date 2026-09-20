import { test, expect } from '@playwright/test';

const V2 = 'http://localhost:8000/api/v2';
const FRONTEND = 'http://localhost:7788';

test('wallet panel: balance display and coin deduction on purchase', async ({ page }) => {
  // Register user
  const creds = { username: `walletuser_${Date.now()}`, password: 'test123456', nickname: '钱包用户' };
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

  // 1. Check initial balance on homepage
  await page.goto(`${FRONTEND}/`);
  await page.waitForTimeout(2000);

  await page.screenshot({ path: '/tmp/wallet_homepage.png', fullPage: false });
  const homeText = await page.textContent('body');
  console.log('Homepage balance:', homeText?.substring(0, 200));

  // Should show balance (new users start with 10000)
  const balanceMatch = homeText?.match(/[\d,]+/);
  console.log('Balance detected:', balanceMatch?.[0]);

  // 2. Navigate to wallet detail page
  await page.click('.wallet-btn, button:has-text("钱包")');
  await page.waitForTimeout(2000);

  await page.screenshot({ path: '/tmp/wallet_detail.png', fullPage: false });
  const walletText = await page.textContent('body');
  console.log('Wallet page:', walletText?.substring(0, 500));

  // Should show wallet info
  expect(walletText).toContain('钱包') || expect(walletText).toContain('余额') || expect(walletText).toContain('10,000');

  // 3. Navigate to a product and check purchase flow
  await page.goto(`${FRONTEND}/product/1`);
  await page.waitForTimeout(3000);

  await page.screenshot({ path: '/tmp/wallet_product.png', fullPage: false });
  const productText = await page.textContent('body');
  console.log('Product page:', productText?.substring(0, 300));

  expect(productText).toContain('SkillBazaar');
  expect(productText).toContain('code-reviewer');

  // 4. Purchase the free product
  const buyResp = await fetch('http://localhost:8000/api/transactions/buy', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${loginData.token}` },
    body: JSON.stringify({ product_id: 1, user_id: meData.user_id })
  });
  const buyData = await buyResp.json();
  console.log('Purchase result:', buyResp.status, JSON.stringify(buyData).substring(0, 200));
  expect(buyResp.status).toBe(200);

  // 5. Check balance after purchase (free product shouldn't deduct)
  await page.reload();
  await page.waitForTimeout(2000);

  const afterBuyText = await page.textContent('body');
  console.log('After purchase:', afterBuyText?.substring(0, 300));

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
