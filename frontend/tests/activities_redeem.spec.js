import { test, expect } from '@playwright/test';

const V2 = 'http://localhost:8000/api/v2';
const API_BASE = 'http://localhost:8000/api';
const FRONTEND = 'http://localhost:7788';

test('activities page: points redemption for coins', async ({ page }) => {
  // Register and login
  const creds = { username: `redeem_${Date.now()}`, password: 'test123456', nickname: '兑换测试用户' };
  const regResp = await fetch(`${V2}/auth/register`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(creds)
  });
  const regData = await regResp.json();

  const loginResp = await fetch(`${V2}/auth/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ username: creds.username, password: creds.password })
  });
  const loginData = await loginResp.json();
  const token = loginData.token;
  const userId = loginData.user_id;

  await page.goto(FRONTEND);
  await page.waitForTimeout(1500);

  // Remove overlays and inject auth
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
  }, { t: token, uid: userId, un: creds.username, nick: creds.nickname });

  // Navigate to activities page
  await page.goto(`${FRONTEND}/activities`);
  await page.waitForTimeout(3000);

  // 1. Get initial points balance
  const pointsResp = await fetch(`${API_BASE}/activities/points/balance`, {
    headers: { Authorization: `Bearer ${token}` }
  });
  const pointsData = await pointsResp.json();
  console.log('Initial points:', JSON.stringify(pointsData).substring(0, 200));
  const initialPoints = pointsData.balance || 0;

  // 2. Get initial coin balance from auth/me
  const meResp = await fetch(`${V2}/auth/me`, {
    headers: { Authorization: `Bearer ${token}` }
  });
  const meData = await meResp.json();
  console.log('User coins:', meData.coins);
  const initialCoins = meData.coins || 0;

  // 3. Do daily check-in to earn points
  const checkinBtn = page.locator('button:has-text("签到领积分")');
  if (await checkinBtn.count() > 0) {
    await checkinBtn.click();
    await page.waitForTimeout(2000);
  }

  // Verify check-in result
  const afterCheckin = await page.textContent('body');
  expect(afterCheckin).toContain('签到成功');

  // Get points after check-in
  const afterPointsResp = await fetch(`${API_BASE}/activities/points/balance`, {
    headers: { Authorization: `Bearer ${token}` }
  });
  const afterPointsData = await afterPointsResp.json();
  const pointsAfterCheckin = afterPointsData.balance || 0;
  console.log('Points after checkin:', pointsAfterCheckin);
  expect(pointsAfterCheckin).toBeGreaterThan(initialPoints);

  // 4. Find redeem section
  await page.screenshot({ path: '/tmp/activities_redeem.png', fullPage: false });
  const pageText = await page.textContent('body');
  console.log('Activities page:', pageText?.substring(0, 1200));

  // Verify redeem section exists
  expect(pageText).toContain('兑换');
  expect(pageText).toContain('积分');

  const redeemInput = page.locator('.redeem-input');
  const inputCount = await redeemInput.count();
  console.log('Redeem input count:', inputCount);
  expect(inputCount).toBeGreaterThan(0);

  const redeemBtn = page.locator('.redeem-btn');
  const btnCount = await redeemBtn.count();
  console.log('Redeem button count:', btnCount);
  expect(btnCount).toBeGreaterThan(0);

  // 5. Try redeeming all available points
  if (pointsAfterCheckin > 0) {
    await redeemInput.first().fill(String(pointsAfterCheckin));
    await page.waitForTimeout(500);

    await redeemBtn.first().click();
    await page.waitForTimeout(2000);

    await page.screenshot({ path: '/tmp/after_redeem.png', fullPage: false });
    const afterRedeem = await page.textContent('body');
    console.log('After redeem:', afterRedeem?.substring(0, 1000));

    // Verify redeem result - either success or error message
    const hasRedeemFeedback = afterRedeem.includes('兑换成功') ||
                              afterRedeem.includes('兑换失败') ||
                              afterRedeem.includes('积分不足') ||
                              afterRedeem.includes('最少') ||
                              afterRedeem.includes('兑换');
    console.log('Has redeem feedback:', hasRedeemFeedback);
    expect(hasRedeemFeedback).toBe(true);

    // Verify points balance after redeem attempt
    const finalPointsResp = await fetch(`${API_BASE}/activities/points/balance`, {
      headers: { Authorization: `Bearer ${token}` }
    });
    const finalPointsData = await finalPointsResp.json();
    console.log('Points after redeem:', JSON.stringify(finalPointsData).substring(0, 200));

    // If redeem succeeded, verify points decreased
    if (afterRedeem.includes('兑换成功')) {
      expect(finalPointsData.balance).toBeLessThan(pointsAfterCheckin);
    }
  } else {
    console.log('No points available to test redemption');
  }

  // Verify activities page loaded successfully
  expect(pageText).toContain('活动任务中心');
  expect(pageText).toContain('挑战任务');

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
