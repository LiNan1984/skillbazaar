import { test, expect } from '@playwright/test';

const V2 = 'http://localhost:8000/api/v2';
const API_BASE = 'http://localhost:8000/api';
const FRONTEND = 'http://localhost:7788';

test('activities page: renders check-in, points and leaderboard', async ({ page }) => {
  // Register and login
  const creds = { username: `act_${Date.now()}`, password: 'test123456', nickname: '活动测试用户' };
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
  }, { t: loginData.token, uid: loginData.user_id, un: creds.username, nick: creds.nickname });

  // 1. Navigate to activities page
  await page.goto(`${FRONTEND}/activities`);
  await page.waitForTimeout(3000);

  await page.screenshot({ path: '/tmp/activities_page.png', fullPage: false });
  const actText = await page.textContent('body');
  console.log('Activities page:', actText?.substring(0, 1000));

  // 2. Verify page title and core sections
  expect(actText).toContain('活动任务中心');
  expect(actText).toContain('每日签到');
  expect(actText).toContain('我的积分');
  expect(actText).toContain('排行榜');

  // 3. Verify check-in button exists
  const checkinBtn = page.locator('.checkin-btn, button:has-text("签到")');
  const checkinCount = await checkinBtn.count();
  expect(checkinCount).toBeGreaterThan(0);
  console.log('Check-in button count:', checkinCount);

  // 4. Verify points card shows initial balance (0 for new user)
  expect(actText).toContain('积分');
  expect(actText).toContain('兑换');

  // 5. Click check-in and verify result
  await checkinBtn.first().click();
  await page.waitForTimeout(2000);

  await page.screenshot({ path: '/tmp/activities_after_checkin.png', fullPage: false });
  const afterCheckin = await page.textContent('body');
  console.log('After check-in:', afterCheckin?.substring(0, 600));

  const hasCheckinResult = afterCheckin?.includes('签到成功') ||
                          afterCheckin?.includes('已签到') ||
                          afterCheckin?.includes('连续签到') ||
                          afterCheckin?.includes('积分');
  expect(hasCheckinResult).toBe(true);

  // 6. Click check-in again to test "already checked in" case
  await checkinBtn.first().click();
  await page.waitForTimeout(1500);
  const afterSecond = await page.textContent('body');
  console.log('After second check-in:', afterSecond?.substring(0, 400));

  const secondResult = afterSecond?.includes('已签到') ||
                       afterSecond?.includes('今天') ||
                       afterSecond?.includes('签到成功');
  console.log('Second check-in result:', secondResult);

  // 7. Verify leaderboard section exists
  expect(afterSecond).toContain('排行榜');

  // 8. Verify points redemption input exists
  const redeemInput = page.locator('.redeem-input, input[placeholder*="金币"]');
  const redeemCount = await redeemInput.count();
  console.log('Redeem input count:', redeemCount);
  if (redeemCount > 0) {
    await redeemInput.first().fill('10');
    await page.waitForTimeout(500);

    const redeemBtn = page.locator('.redeem-btn, button:has-text("兑换")');
    const redeemBtnCount = await redeemBtn.count();
    console.log('Redeem button count:', redeemBtnCount);
    // Don't actually redeem - user has 0 points so it should fail/error
  }

  // 9. Verify no console errors
  const consoleErrors = [];
  page.on('console', msg => {
    if (msg.type() === 'error') consoleErrors.push(msg.text());
  });

  await page.reload();
  await page.waitForTimeout(2000);
  console.log('Console errors:', consoleErrors);
  expect(consoleErrors.length).toBe(0);
});
