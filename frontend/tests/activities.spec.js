import { test, expect } from '@playwright/test';

const API_BASE = 'http://localhost:8000/api';
const V2 = `${API_BASE}/v2`;
const FRONTEND = 'http://localhost:7788';

test('activities page: check-in, points, leaderboard', async ({ page }) => {
  // Register and login
  const regResp = await fetch(`${V2}/auth/register`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ username: `act_${Date.now()}`, password: 'test123456', nickname: '活动测试用户' })
  });
  const regData = await regResp.json();

  const loginResp = await fetch(`${V2}/auth/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ username: regData.username, password: 'test123456' })
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

  await page.evaluate(({ t, uid }) => {
    localStorage.setItem('skillbazaar_token', t);
    localStorage.setItem('skillbazaar_user_id', uid);
    localStorage.setItem('skillbazaar_username', 'actuser');
    localStorage.setItem('skillbazaar_nickname', '活动测试用户');
  }, { t: token, uid: userId });

  // Navigate to activities page
  await page.goto(`${FRONTEND}/activities`);
  await page.waitForTimeout(3000);

  await page.screenshot({ path: '/tmp/activities_page.png', fullPage: false });
  const bodyText = await page.textContent('body');
  console.log('Activities page:', bodyText?.substring(0, 1200));

  // Verify page title
  expect(bodyText).toContain('活动任务中心');

  // Verify points balance is shown (frontend uses /api/activities/points/balance)
  const pointsResp = await fetch(`${API_BASE}/activities/points/balance`, {
    headers: { Authorization: `Bearer ${token}` }
  });
  const pointsData = await pointsResp.json();
  console.log('Points balance:', JSON.stringify(pointsData).substring(0, 200));
  expect(pointsData.user_id).toBe(userId);
  expect(pointsData.balance).toBeDefined();

  // Get initial points
  const initialBalance = pointsData.balance || 0;

  // Click daily check-in
  const checkinBtn = page.locator('button:has-text("签到领积分")');
  await checkinBtn.click();
  await page.waitForTimeout(2000);

  await page.screenshot({ path: '/tmp/after_checkin.png', fullPage: false });
  const afterCheckin = await page.textContent('body');
  console.log('After check-in:', afterCheckin?.substring(0, 800));

  // Verify check-in result
  expect(afterCheckin).toContain('签到成功');

  // Verify points increased
  const afterPointsResp = await fetch(`${API_BASE}/activities/points/balance`, {
    headers: { Authorization: `Bearer ${token}` }
  });
  const afterPointsData = await afterPointsResp.json();
  console.log('Points after checkin:', JSON.stringify(afterPointsData).substring(0, 200));
  expect(afterPointsData.balance).toBeGreaterThan(initialBalance);

  // Verify streak info
  expect(afterCheckin).toContain('连续签到');

  // Try to check in again (should fail or show already checked in)
  const checkinResultBefore = await page.textContent('body');
  await checkinBtn.click();
  await page.waitForTimeout(1500);
  const checkinResultAfter = await page.textContent('body');
  console.log('Double checkin result:', checkinResultAfter?.substring(0, 500));

  // Verify leaderboard is shown (or "暂无排行数据")
  const hasLeaderboard = afterCheckin.includes('排行榜') || afterCheckin.includes('暂无排行数据');
  expect(hasLeaderboard).toBe(true);

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
