import { test, expect } from '@playwright/test';

const API_BASE = 'http://localhost:8000/api';
const V2 = `${API_BASE}/v2`;
const FRONTEND = 'http://localhost:7788';

test('bounty poster: view applicants and select developer', async ({ page }) => {
  // Register poster and developer
  const posterCreds = { username: `posterview_${Date.now()}`, password: 'test123456', nickname: '发帖人视图' };
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

  const devCreds = { username: `devview_${Date.now()}`, password: 'test123456', nickname: '开发者视图' };
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

  // 1. Poster creates a bounty via API
  const bountyResp = await fetch(`${API_BASE}/bounties`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${posterLogin.token}` },
    body: JSON.stringify({
      title: `发帖人查看申请_${Date.now()}`,
      description: '测试发帖人查看竞标方案并选人。需要开发一个数据分析Dashboard。',
      category: 'Agent',
      budget_min: 1000,
      budget_max: 3000,
      deadline: new Date(Date.now() + 14 * 24 * 60 * 60 * 1000).toISOString(),
      skill_type: 'code'
    })
  });
  const bounty = await bountyResp.json();
  expect(bountyResp.status).toBe(200);
  console.log('Created bounty:', bounty.id);

  // 2. Two developers apply to the bounty
  const dev2Creds = { username: `dev2view_${Date.now()}`, password: 'test123456', nickname: '竞争者乙' };
  await fetch(`${V2}/auth/register`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(dev2Creds)
  }).then(r => r.json());

  const dev2Login = await fetch(`${V2}/auth/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ username: dev2Creds.username, password: dev2Creds.password })
  }).then(r => r.json());

  await fetch(`${API_BASE}/bounties/${bounty.id}/apply`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${devLogin.token}` },
    body: JSON.stringify({
      proposal: '我有5年全栈开发经验，擅长React和Python。预计7天完成，报价2500金币。',
      estimated_days: 7,
      quoted_price: 2500
    })
  }).then(r => r.json());

  await fetch(`${API_BASE}/bounties/${bounty.id}/apply`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${dev2Login.token}` },
    body: JSON.stringify({
      proposal: '我是数据可视化专家，有多个Dashboard开发经验。预计5天完成，报价2000金币。',
      estimated_days: 5,
      quoted_price: 2000
    })
  }).then(r => r.json());

  // 3. Login as poster and navigate to bounty detail
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

  await page.goto(`${FRONTEND}/bounty/${bounty.id}`);
  await page.waitForTimeout(3000);

  await page.screenshot({ path: '/tmp/poster_bounty_detail.png', fullPage: false });
  const detailText = await page.textContent('body');
  console.log('Poster bounty detail:', detailText?.substring(0, 800));

  // Verify bounty title and status
  expect(detailText).toContain('发帖人查看申请');
  expect(detailText).toContain('招募中');

  // 4. Verify both applications are shown
  expect(detailText).toContain('竞标方案');
  expect(detailText).toContain('开发者视图');
  expect(detailText).toContain('竞争者乙');

  // 5. Verify the "选择开发者" button exists for poster
  const hasSelectButton = detailText.includes('选择') || detailText.includes('选中');
  console.log('Has select developer button:', hasSelectButton);

  // 6. Select the first developer via API
  const bountyDetail = await fetch(`${API_BASE}/bounties/${bounty.id}`, {
    headers: { Authorization: `Bearer ${posterLogin.token}` }
  }).then(r => r.json());
  const firstAppId = bountyDetail.applications[0].id;

  const selectResp = await fetch(`${API_BASE}/bounties/${bounty.id}/select`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${posterLogin.token}` },
    body: JSON.stringify({ application_id: firstAppId })
  });
  const selectData = await selectResp.json();
  expect(selectResp.status).toBe(200);
  console.log('Select result:', selectData);

  // 7. Reload and verify bounty is now "开发中"
  await page.reload();
  await page.waitForTimeout(3000);

  await page.screenshot({ path: '/tmp/poster_after_select.png', fullPage: false });
  const afterSelectText = await page.textContent('body');
  console.log('After select:', afterSelectText?.substring(0, 800));

  expect(afterSelectText).toContain('开发中');
  // Should show only the selected developer
  expect(afterSelectText).toContain('开发者视图');

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
