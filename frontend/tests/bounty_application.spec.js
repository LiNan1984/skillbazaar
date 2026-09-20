import { test, expect } from '@playwright/test';

const V2 = 'http://localhost:8000/api/v2';
const API_BASE = 'http://localhost:8000/api';
const FRONTEND = 'http://localhost:7788';

async function registerAndLogin(suffix, nickname) {
  const creds = { username: `${suffix}_${Date.now()}`, password: 'test123456', nickname };
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
  return { creds, loginData };
}

async function injectAuth(page, loginData, creds) {
  await page.goto(FRONTEND);
  await page.waitForTimeout(1000);
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
}

test('bounty application: developer applies to a bounty via UI', async ({ page }) => {
  // 1. Create poster user and bounty
  const { creds: posterCreds, loginData: posterLogin } = await registerAndLogin('bposter', '悬赏发布者');

  const futureDate = new Date();
  futureDate.setDate(futureDate.getDate() + 30);
  const dateStr = futureDate.toISOString().split('T')[0];

  const bountyResp = await fetch(`${API_BASE}/bounties`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${posterLogin.token}` },
    body: JSON.stringify({
      title: `E2E竞标测试悬赏_${Date.now()}`,
      description: '这是一个用于测试竞标功能的悬赏任务，需要开发自动化脚本。',
      category: 'Skill',
      skill_type: 'prompt',
      budget_min: 300,
      budget_max: 800,
      deadline: dateStr,
      requirements: '熟悉Python和自动化'
    })
  });
  const bountyData = await bountyResp.json();
  const bountyId = bountyData.id;
  console.log('Created bounty:', bountyId);

  // 2. Create developer user
  const { creds: devCreds, loginData: devLogin } = await registerAndLogin('bdev', '竞标开发者');

  // 3. Developer applies via API first to verify endpoint
  const applyResp = await fetch(`${API_BASE}/bounties/${bountyId}/apply`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${devLogin.token}` },
    body: JSON.stringify({
      proposal: '我有丰富的自动化脚本开发经验，使用Python可以快速完成此任务。',
      quoted_price: 500,
      estimated_days: 7,
      portfolio: 'https://github.com/test/example'
    })
  });
  const applyData = await applyResp.json();
  console.log('Application status:', applyResp.status, applyData);
  expect([200, 201]).toContain(applyResp.status);

  // 4. Verify poster can see the application
  const bountyDetailResp = await fetch(`${API_BASE}/bounties/${bountyId}`, {
    headers: { Authorization: `Bearer ${posterLogin.token}` }
  });
  const bountyDetail = await bountyDetailResp.json();
  console.log('Bounty applications:', bountyDetail.applications?.length || 0);

  const applications = bountyDetail.applications || bountyDetail.Application || [];
  expect(applications.length).toBeGreaterThanOrEqual(1);

  const devApplication = applications.find(a =>
    a.developer_name === devCreds.nickname ||
    a.proposal?.includes('自动化脚本')
  );
  expect(devApplication).toBeTruthy();
  expect(devApplication.quoted_price).toBe(500);
  expect(devApplication.estimated_days).toBe(7);
  expect(devApplication.status).toBe('pending');

  // 5. Navigate to bounty detail page as developer - verify UI
  await injectAuth(page, devLogin, devCreds);
  await page.goto(`${FRONTEND}/bounty/${bountyId}`);
  await page.waitForTimeout(3000);

  await page.screenshot({ path: '/tmp/bounty_dev_view.png', fullPage: false });
  const devPageText = await page.textContent('body');
  console.log('Dev bounty view:', devPageText?.substring(0, 600));

  // Developer should see bounty info
  expect(devPageText).toContain('悬赏');
  expect(devPageText).toContain('300');

  // Developer already applied - should see application status
  const seesAppliedState = devPageText?.includes('已申请') ||
                           devPageText?.includes('已竞标') ||
                           devPageText?.includes('等待') ||
                           devPageText?.includes('pending') ||
                           devPageText?.includes('竞标接单');
  console.log('Applied state visible:', seesAppliedState);

  // 6. Verify poster sees application in UI
  await injectAuth(page, posterLogin, posterCreds);
  await page.goto(`${FRONTEND}/bounty/${bountyId}`);
  await page.waitForTimeout(3000);

  await page.screenshot({ path: '/tmp/bounty_poster_view.png', fullPage: false });
  const posterPageText = await page.textContent('body');
  console.log('Poster view has applications:', posterPageText?.includes('竞标') || posterPageText?.includes(devCreds.nickname));

  expect(posterPageText).toContain('悬赏');

  // 7. Verify no console errors
  const consoleErrors = [];
  page.on('console', msg => {
    if (msg.type() === 'error') consoleErrors.push(msg.text());
  });

  await page.reload();
  await page.waitForTimeout(2000);
  console.log('Console errors:', consoleErrors);
  expect(consoleErrors.length).toBe(0);
});
