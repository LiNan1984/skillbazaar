import { test, expect } from '@playwright/test';

const API_BASE = 'http://localhost:8000/api';
const V2 = `${API_BASE}/v2`;
const FRONTEND = 'http://localhost:7788';

test('bounty status filter tabs: open, all, and completed', async ({ page }) => {
  // Register user A (bounty poster) and user B (developer)
  const posterCreds = { username: `filterposter_${Date.now()}`, password: 'test123456', nickname: '发帖人' };
  await fetch(`${V2}/auth/register`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(posterCreds)
  }).then(r => r.json());

  const posterLogin = await fetch(`${V2}/auth/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ username: posterCreds.username, password: posterCreds.password })
  }).then(r => r.json());
  const posterMe = await fetch(`${V2}/auth/me`, {
    headers: { Authorization: `Bearer ${posterLogin.token}` }
  }).then(r => r.json());

  const devCreds = { username: `filterdev_${Date.now()}`, password: 'test123456', nickname: '开发者甲' };
  await fetch(`${V2}/auth/register`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(devCreds)
  }).then(r => r.json());

  const devLogin = await fetch(`${V2}/auth/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ username: devCreds.username, password: devCreds.password })
  }).then(r => r.json());
  const devMe = await fetch(`${V2}/auth/me`, {
    headers: { Authorization: `Bearer ${devLogin.token}` }
  }).then(r => r.json());

  // 1. Create an open bounty (招募中)
  const openBountyResp = await fetch(`${API_BASE}/bounties`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${posterLogin.token}` },
    body: JSON.stringify({
      title: `筛选测试_招募中_${Date.now()}`,
      description: '测试招募中筛选的悬赏任务。',
      category: 'Skill',
      budget_min: 200,
      budget_max: 500,
      deadline: new Date(Date.now() + 7 * 24 * 60 * 60 * 1000).toISOString(),
      skill_type: 'prompt'
    })
  });
  const openBounty = await openBountyResp.json();
  console.log('Open bounty:', openBounty.id);
  expect(openBountyResp.status).toBe(200);

  // 2. Create a completed bounty via API (go through full lifecycle)
  const completedBountyResp = await fetch(`${API_BASE}/bounties`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${posterLogin.token}` },
    body: JSON.stringify({
      title: `筛选测试_已完成_${Date.now()}`,
      description: '测试已完成筛选的悬赏任务。',
      category: 'Agent',
      budget_min: 300,
      budget_max: 800,
      deadline: new Date(Date.now() + 14 * 24 * 60 * 60 * 1000).toISOString(),
      skill_type: 'code'
    })
  });
  const completedBounty = await completedBountyResp.json();
  console.log('Completed bounty:', completedBounty.id);
  expect(completedBountyResp.status).toBe(200);

  // Dev applies to the completed bounty
  await fetch(`${API_BASE}/bounties/${completedBounty.id}/apply`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${devLogin.token}` },
    body: JSON.stringify({
      proposal: '我有丰富的Agent开发经验，可以高质量完成此任务。',
      estimated_days: 5,
      quoted_price: 600
    })
  }).then(r => r.json());

  // Poster selects the dev
  const applications = await fetch(`${API_BASE}/bounties/${completedBounty.id}`, {
    headers: { Authorization: `Bearer ${posterLogin.token}` }
  }).then(r => r.json());
  const appId = applications.applications[0].id;

  await fetch(`${API_BASE}/bounties/${completedBounty.id}/select`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${posterLogin.token}` },
    body: JSON.stringify({ application_id: appId })
  }).then(r => r.json());

  // Dev delivers
  await fetch(`${API_BASE}/bounties/${completedBounty.id}/deliver`, {
    method: 'POST',
    headers: { Authorization: `Bearer ${devLogin.token}` },
    body: JSON.stringify({
      description: '已完成开发，包含完整的Agent代码和文档。'
    })
  }).then(r => r.json());

  // Poster accepts delivery → bounty becomes "completed"
  const bountyAfterDeliver = await fetch(`${API_BASE}/bounties/${completedBounty.id}`, {
    headers: { Authorization: `Bearer ${posterLogin.token}` }
  }).then(r => r.json());
  const deliveryId = bountyAfterDeliver.deliveries[0].id;

  await fetch(`${API_BASE}/bounties/${completedBounty.id}/review`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${posterLogin.token}` },
    body: JSON.stringify({ delivery_id: deliveryId, accept: true })
  }).then(r => r.json());

  // Login as poster for UI testing
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
  }, { t: posterLogin.token, uid: posterMe.user_id, un: posterCreds.username, nick: posterCreds.nickname });

  // 3. Navigate to bounty page
  await page.goto(`${FRONTEND}/bounties`);
  await page.waitForTimeout(3000);

  await page.screenshot({ path: '/tmp/bounty_filters_default.png', fullPage: false });
  const defaultText = await page.textContent('body');
  console.log('Default bounty page:', defaultText?.substring(0, 600));

  // Default filter is "招募中" (open) - should show the open bounty
  expect(defaultText).toContain('筛选测试_招募中');
  expect(defaultText).not.toContain('筛选测试_已完成');

  // 4. Click "全部" tab
  await page.click('button:has-text("全部")');
  await page.waitForTimeout(2000);

  await page.screenshot({ path: '/tmp/bounty_filters_all.png', fullPage: false });
  const allText = await page.textContent('body');
  console.log('All bounties:', allText?.substring(0, 600));

  expect(allText).toContain('筛选测试_招募中');
  expect(allText).toContain('筛选测试_已完成');

  // 5. Click "已完成" tab
  await page.click('button:has-text("已完成")');
  await page.waitForTimeout(2000);

  await page.screenshot({ path: '/tmp/bounty_filters_completed.png', fullPage: false });
  const completedText = await page.textContent('body');
  console.log('Completed bounties:', completedText?.substring(0, 600));

  expect(completedText).toContain('筛选测试_已完成');
  expect(completedText).not.toContain('筛选测试_招募中');

  // 6. Click "招募中" tab to go back
  await page.click('button:has-text("招募中")');
  await page.waitForTimeout(2000);

  const openText = await page.textContent('body');
  expect(openText).toContain('筛选测试_招募中');
  expect(openText).not.toContain('筛选测试_已完成');

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
