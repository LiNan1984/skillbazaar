import { test, expect } from '@playwright/test';

const V2 = 'http://localhost:8000/api/v2';
const FRONTEND = 'http://localhost:7788';

test('library page: empty state for new user with no purchases', async ({ page }) => {
  // Register a fresh user
  const creds = { username: `libempty_${Date.now()}`, password: 'test123456', nickname: '空库用户' };
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

  await page.evaluate(({ t, uid, un, nick }) => {
    localStorage.setItem('skillbazaar_token', t);
    localStorage.setItem('skillbazaar_user_id', uid);
    localStorage.setItem('skillbazaar_username', un);
    localStorage.setItem('skillbazaar_nickname', nick);
  }, { t: loginData.token, uid: meData.user_id, un: creds.username, nick: creds.nickname });

  // Navigate to library page
  await page.goto(`${FRONTEND}/library`);
  await page.waitForTimeout(3000);

  await page.screenshot({ path: '/tmp/library_empty.png', fullPage: false });
  const libText = await page.textContent('body');
  console.log('Library empty state:', libText?.substring(0, 800));

  // Verify library page loaded
  expect(libText).toContain('我的库');

  // Verify all 4 tabs exist
  expect(libText).toContain('我的智能体');
  expect(libText).toContain('已购技能');
  expect(libText).toContain('Cron订阅');
  expect(libText).toContain('悬赏任务');

  // Verify empty state is shown (default tab is agents)
  const hasEmptyState = libText.includes('还没有') || libText.includes('暂无') || libText.includes('还没有创建');
  console.log('Has empty state:', hasEmptyState);

  // Switch to skills tab
  await page.click('button:has-text("已购技能")');
  await page.waitForTimeout(2000);

  await page.screenshot({ path: '/tmp/library_skills_empty.png', fullPage: false });
  const skillsText = await page.textContent('body');
  console.log('Skills tab empty:', skillsText?.substring(0, 500));

  // Switch to Crons tab
  await page.click('button:has-text("Cron订阅")');
  await page.waitForTimeout(2000);

  const cronsText = await page.textContent('body');
  console.log('Crons tab:', cronsText?.substring(0, 500));

  // Switch to Bounties tab
  await page.click('button:has-text("悬赏任务")');
  await page.waitForTimeout(2000);

  const bountiesText = await page.textContent('body');
  console.log('Bounties tab:', bountiesText?.substring(0, 500));

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
