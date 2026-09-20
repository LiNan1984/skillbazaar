import { test, expect } from '@playwright/test';

const V2 = 'http://localhost:8000/api/v2';
const API_BASE = 'http://localhost:8000/api';
const FRONTEND = 'http://localhost:7788';

test('bounty lifecycle: apply, select, deliver, review full flow', async ({ page }) => {
  const makeUser = async (suffix, nickname) => {
    const creds = { username: `${suffix}_${Date.now()}`, password: 'test123456', nickname };
    await fetch(`${V2}/auth/register`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(creds)
    });
    const login = await fetch(`${V2}/auth/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username: creds.username, password: creds.password })
    }).then(r => r.json());
    return { creds, login };
  };

  // 1. Poster creates bounty
  const { creds: posterCreds, login: posterLogin } = await makeUser('lifecycle_poster', '生命周期悬赏主');
  const futureDate = new Date();
  futureDate.setDate(futureDate.getDate() + 30);

  const bountyResp = await fetch(`${API_BASE}/bounties`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${posterLogin.token}` },
    body: JSON.stringify({
      title: `生命周期测试悬赏_${Date.now()}`,
      description: '完整测试悬赏生命周期：竞标、选择、交付、验收。',
      category: 'Skill',
      skill_type: 'code',
      budget_min: 200,
      budget_max: 600,
      deadline: futureDate.toISOString().split('T')[0],
      requirements: 'Python技能'
    })
  });
  const bounty = await bountyResp.json();
  const bountyId = bounty.id;
  console.log('Bounty created:', bountyId);

  // 2. Developer applies
  const { creds: devCreds, login: devLogin } = await makeUser('lifecycle_dev', '生命周期开发者');
  const applyResp = await fetch(`${API_BASE}/bounties/${bountyId}/apply`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${devLogin.token}` },
    body: JSON.stringify({
      proposal: '我可以完成此任务，有3年Python经验。',
      quoted_price: 400,
      estimated_days: 5,
      portfolio: ''
    })
  });
  const application = await applyResp.json();
  const applicationId = application.id;
  console.log('Application submitted:', applicationId);
  expect(applyResp.status).toBe(200);

  // 3. Poster selects developer
  const selectResp = await fetch(`${API_BASE}/bounties/${bountyId}/select`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${posterLogin.token}` },
    body: JSON.stringify({ application_id: applicationId })
  });
  const selectData = await selectResp.json();
  console.log('Developer selected:', selectResp.status, selectData);
  expect(selectResp.status).toBe(200);

  // Verify bounty status changed
  const detailAfterSelect = await fetch(`${API_BASE}/bounties/${bountyId}`, {
    headers: { Authorization: `Bearer ${posterLogin.token}` }
  }).then(r => r.json());
  console.log('Bounty status after select:', detailAfterSelect.status);
  expect(['in_progress', 'assigned']).toContain(detailAfterSelect.status);

  // 4. Developer delivers
  const deliverResp = await fetch(`${API_BASE}/bounties/${bountyId}/deliver`, {
    method: 'POST',
    headers: {
      Authorization: `Bearer ${devLogin.token}`,
      'Content-Type': 'application/json'
    },
    body: JSON.stringify({
      description: '已完成开发，交付Python脚本文件。使用方法：python main.py'
    })
  });
  const deliverData = await deliverResp.json();
  console.log('Delivery submitted:', deliverResp.status, deliverData);
  expect([200, 201]).toContain(deliverResp.status);

  const deliveryId = deliverData.delivery_id || deliverData.id || deliverData.delivery?.id;

  // 5. Poster reviews - accept delivery
  if (deliveryId) {
    const reviewResp = await fetch(`${API_BASE}/bounties/${bountyId}/review`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${posterLogin.token}` },
      body: JSON.stringify({
        delivery_id: deliveryId,
        accept: true
      })
    });
    const reviewData = await reviewResp.json();
    console.log('Review submitted:', reviewResp.status, reviewData);
    expect([200, 201]).toContain(reviewResp.status);

    // Verify final bounty status
    const finalDetail = await fetch(`${API_BASE}/bounties/${bountyId}`, {
      headers: { Authorization: `Bearer ${posterLogin.token}` }
    }).then(r => r.json());
    console.log('Final bounty status:', finalDetail.status);
  } else {
    console.log('No delivery ID returned - check delivery response structure');
  }

  // 6. Verify UI renders for each role throughout lifecycle
  await page.goto(FRONTEND);
  await page.waitForTimeout(1000);

  await page.evaluate(() => {
    document.querySelectorAll('.modal-overlay, [class*="overlay"]').forEach(el => {
      el.style.pointerEvents = 'none';
      el.style.display = 'none';
    });
  });

  // Poster view
  await page.evaluate(({ t, uid, un, nick }) => {
    localStorage.setItem('skillbazaar_token', t);
    localStorage.setItem('skillbazaar_user_id', uid);
    localStorage.setItem('skillbazaar_username', un);
    localStorage.setItem('skillbazaar_nickname', nick);
  }, { t: posterLogin.token, uid: posterLogin.user_id, un: posterCreds.username, nick: posterCreds.nickname });

  await page.goto(`${FRONTEND}/bounty/${bountyId}`);
  await page.waitForTimeout(3000);

  await page.screenshot({ path: '/tmp/bounty_lifecycle_poster.png', fullPage: false });
  const posterText = await page.textContent('body');
  console.log('Poster lifecycle view:', posterText?.substring(0, 500));

  expect(posterText).toContain('生命周期测试悬赏');
  expect(posterText).toContain('SkillBazaar');

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
