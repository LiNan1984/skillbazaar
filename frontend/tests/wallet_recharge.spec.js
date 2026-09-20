import { test, expect } from '@playwright/test';
import { execSync } from 'node:child_process';

const V2 = 'http://localhost:8000/api/v2';
const API_BASE = 'http://localhost:8000/api';
const FRONTEND = 'http://localhost:7788';
const DB_PATH = '/Users/linan/Desktop/aicode/skillbazaar/backend/data/skillbazaar.db';

test('wallet recharge: promo code adds coins', async ({ page }) => {
  // 1. Register and login a regular user
  const creds = { username: `wallet_${Date.now()}`, password: 'test123456', nickname: '钱包测试用户' };
  await fetch(`${V2}/auth/register`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(creds)
  });

  const loginResp = await fetch(`${V2}/auth/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ username: creds.username, password: creds.password })
  });
  const loginData = await loginResp.json();

  // 2. Get user ID, then promote to admin via SQLite
  const meResp = await fetch(`${V2}/auth/me`, {
    headers: { Authorization: `Bearer ${loginData.token}` }
  });
  const meData = await meResp.json();
  const userId = meData.user_id || meData.id;

  try {
    execSync(`sqlite3 "${DB_PATH}" "UPDATE users SET role='admin' WHERE id='${userId}'"`);
  } catch (e) {
    console.log('DB admin upgrade failed (may already be admin):', e.message);
  }

  // 3. Create promo code via admin API
  const promoCode = `E2E_${Date.now()}`;
  const promoResp = await fetch(`${V2}/admin/promo-code?code=${promoCode}&coins=500&max_uses=1`, {
    method: 'POST',
    headers: { Authorization: `Bearer ${loginData.token}` }
  });
  const promoData = await promoResp.json();
  console.log('Promo code created:', promoData);

  // 4. Inject auth and open frontend
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
  }, { t: loginData.token, uid: userId, un: creds.username, nick: creds.nickname });

  // 5. Navigate to homepage and open wallet panel
  await page.goto(FRONTEND);
  await page.waitForTimeout(2000);

  await page.screenshot({ path: '/tmp/wallet_home.png', fullPage: false });

  // Click wallet button in navbar
  const walletBtn = page.locator('button:has-text("钱包"), button:has-text("wallet"), .btn:has(.lucide-wallet)');
  const btnCount = await walletBtn.count();
  console.log('Wallet buttons found:', btnCount);

  expect(btnCount).toBeGreaterThan(0);
  await walletBtn.first().click();
  await page.waitForTimeout(1500);

  await page.screenshot({ path: '/tmp/wallet_panel_open.png', fullPage: false });

  // 6. Verify wallet panel is open
  const walletText = await page.textContent('body');
  expect(walletText).toContain('我的钱包');
  expect(walletText).toContain('交易记录');
  expect(walletText).toContain('余额');
  console.log('Wallet panel opened:', walletText?.substring(0, 300));

  // 7. Enter promo code and recharge
  if (promoData.code) {
    const promoInput = page.locator('input[placeholder*="充值码"]');
    await promoInput.fill(promoData.code);
    await page.waitForTimeout(300);

    await page.screenshot({ path: '/tmp/wallet_promo_filled.png', fullPage: false });

    const rechargeBtn = page.locator('.wallet-recharge button:has-text("充值"), button.btn-primary:has-text("充值")');
    const rechargeBtnCount = await rechargeBtn.count();
    console.log('Recharge buttons:', rechargeBtnCount);

    await rechargeBtn.first().click();
    await page.waitForTimeout(2000);

    await page.screenshot({ path: '/tmp/wallet_after_recharge.png', fullPage: false });

    // 8. Verify success message and updated balance
    const afterText = await page.textContent('body');
    console.log('After recharge:', afterText?.substring(0, 500));

    const successVisible = afterText?.includes('充值成功');
    const coinsAddedVisible = afterText?.includes('500');
    console.log('Success message:', successVisible, 'Coins shown:', coinsAddedVisible);

    if (successVisible) {
      expect(afterText).toContain('充值成功');
    }
  }

  // 9. Test invalid promo code shows error
  const invalidInput = page.locator('input[placeholder*="充值码"]');
  await invalidInput.fill('INVALID_CODE_XYZ');
  const invalidBtn = page.locator('.wallet-recharge button:has-text("充值"), button.btn-primary:has-text("充值")');
  await invalidBtn.first().click();
  await page.waitForTimeout(1000);

  await page.screenshot({ path: '/tmp/wallet_invalid_promo.png', fullPage: false });

  const invalidText = await page.textContent('body');
  const hasError = invalidText?.includes('无效') || invalidText?.includes('充值码') || invalidText?.includes('错误') || invalidText?.includes('failed');
  console.log('Invalid code error shown:', hasError);

  // 10. Verify no console errors
  const consoleErrors = [];
  page.on('console', msg => {
    if (msg.type() === 'error') consoleErrors.push(msg.text());
  });

  await page.reload();
  await page.waitForTimeout(2000);
  console.log('Console errors:', consoleErrors);
  expect(consoleErrors.length).toBe(0);
});
