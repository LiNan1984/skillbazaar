import { test, expect } from '@playwright/test';

const API_BASE = 'http://localhost:8000/api';
const V2 = `${API_BASE}/v2`;
const FRONTEND = 'http://localhost:7788';

test('dev bounty flow: apply, get selected, deliver, complete', async ({ page }) => {
  // Register poster and developer
  const posterCreds = { username: `devflowposter_${Date.now()}`, password: 'test123456', nickname: '发帖人Dev' };
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

  const devCreds = { username: `devflowdev_${Date.now()}`, password: 'test123456', nickname: '开发者Dev' };
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

  // 1. Poster creates a bounty
  const bountyResp = await fetch(`${API_BASE}/bounties`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${posterLogin.token}` },
    body: JSON.stringify({
      title: `开发者流程测试_${Date.now()}`,
      description: '测试开发者完整接单流程的悬赏任务。需要开发一个简单的API接口。',
      category: 'Agent',
      budget_min: 500,
      budget_max: 1000,
      deadline: new Date(Date.now() + 14 * 24 * 60 * 60 * 1000).toISOString(),
      skill_type: 'code'
    })
  });
  const bounty = await bountyResp.json();
  expect(bountyResp.status).toBe(200);
  console.log('Created bounty:', bounty.id);

  // 2. Developer applies to the bounty (via API)
  const applyResp = await fetch(`${API_BASE}/bounties/${bounty.id}/apply`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${devLogin.token}` },
    body: JSON.stringify({
      proposal: '我有3年Python开发经验，曾开发过多Agent系统。预计5天完成，报价800金币。',
      estimated_days: 5,
      quoted_price: 800
    })
  });
  const applyData = await applyResp.json();
  expect(applyResp.status).toBe(200);
  console.log('Application result:', applyData);

  // 3. Login as developer and navigate to bounty detail
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
  }, { t: devLogin.token, uid: devMe.user_id, un: devCreds.username, nick: devCreds.nickname });

  await page.goto(`${FRONTEND}/bounty/${bounty.id}`);
  await page.waitForTimeout(3000);

  await page.screenshot({ path: '/tmp/dev_bounty_detail.png', fullPage: false });
  const detailText = await page.textContent('body');
  console.log('Dev bounty detail:', detailText?.substring(0, 800));

  expect(detailText).toContain('开发者流程测试');
  // Developer should see their application
  expect(detailText).toContain('开发者Dev');
  expect(detailText).toContain('800');

  // 4. Poster selects the developer (via API)
  const bountyDetail = await fetch(`${API_BASE}/bounties/${bounty.id}`, {
    headers: { Authorization: `Bearer ${posterLogin.token}` }
  }).then(r => r.json());
  const appId = bountyDetail.applications[0].id;

  const selectResp = await fetch(`${API_BASE}/bounties/${bounty.id}/select`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${posterLogin.token}` },
    body: JSON.stringify({ application_id: appId })
  });
  const selectData = await selectResp.json();
  expect(selectResp.status).toBe(200);
  console.log('Select dev result:', selectData);

  // 5. Developer sees "selected" status
  await page.reload();
  await page.waitForTimeout(3000);

  await page.screenshot({ path: '/tmp/dev_selected.png', fullPage: false });
  const selectedText = await page.textContent('body');
  console.log('After selection:', selectedText?.substring(0, 800));

  expect(selectedText).toContain('开发中');

  // 6. Developer delivers the bounty (via API)
  const deliverResp = await fetch(`${API_BASE}/bounties/${bounty.id}/deliver`, {
    method: 'POST',
    headers: { Authorization: `Bearer ${devLogin.token}` },
    body: JSON.stringify({
      description: '已完成API接口开发，包含完整的CRUD操作和文档。'
    })
  });
  const deliverData = await deliverResp.json();
  expect(deliverResp.status).toBe(200);
  console.log('Deliver result:', deliverData);

  // 7. Developer sees "delivered" status
  await page.reload();
  await page.waitForTimeout(3000);

  await page.screenshot({ path: '/tmp/dev_delivered.png', fullPage: false });
  const deliveredText = await page.textContent('body');
  console.log('After deliver:', deliveredText?.substring(0, 800));

  expect(deliveredText).toContain('已交付');

  // 8. Poster accepts the delivery (via API)
  const afterDeliver = await fetch(`${API_BASE}/bounties/${bounty.id}`, {
    headers: { Authorization: `Bearer ${posterLogin.token}` }
  }).then(r => r.json());
  const deliveryId = afterDeliver.deliveries[0].id;

  const reviewResp = await fetch(`${API_BASE}/bounties/${bounty.id}/review`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${posterLogin.token}` },
    body: JSON.stringify({ delivery_id: deliveryId, accept: true })
  });
  const reviewData = await reviewResp.json();
  expect(reviewResp.status).toBe(200);
  console.log('Review accept result:', reviewData);

  // 9. Verify bounty is completed
  const finalBounty = await fetch(`${API_BASE}/bounties/${bounty.id}`, {
    headers: { Authorization: `Bearer ${posterLogin.token}` }
  }).then(r => r.json());
  expect(finalBounty.status).toBe('completed');
  console.log('Final status:', finalBounty.status);

  // 10. Verify bounty appears in poster's "my posted" list
  const myPosted = await fetch(`${API_BASE}/bounties/my/posted?user_id=${posterMe.user_id}`, {
    headers: { Authorization: `Bearer ${posterLogin.token}` }
  }).then(r => r.json());
  expect(myPosted.bounties.some(b => b.id === bounty.id)).toBe(true);
  console.log('My posted count:', myPosted.total);

  // 11. Verify bounty appears in dev's "my applied" list
  const myApplied = await fetch(`${API_BASE}/bounties/my/applied?user_id=${devMe.user_id}`, {
    headers: { Authorization: `Bearer ${devLogin.token}` }
  }).then(r => r.json());
  expect(myApplied.bounties.some(b => b.id === bounty.id)).toBe(true);
  console.log('My applied count:', myApplied.total);

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
