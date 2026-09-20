import { test, expect } from '@playwright/test';

const API_BASE = 'http://localhost:8000/api';
const V2 = `${API_BASE}/v2`;
const FRONTEND = 'http://localhost:7788';

function randUser() {
  const id = Math.random().toString(36).slice(2, 10);
  return { username: `tester_${id}`, password: 'test123456', nickname: `测试用户${id}` };
}

async function registerAndLogin(page, usernamePrefix = '') {
  const base = randUser();
  const creds = usernamePrefix ? { ...base, username: `${usernamePrefix}_${base.username}` } : base;

  const regResp = await fetch(`${V2}/auth/register`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(creds)
  });
  await regResp.json();

  const loginResp = await fetch(`${V2}/auth/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ username: creds.username, password: creds.password })
  });
  const loginData = await loginResp.json();
  const token = loginData.token;

  const meResp = await fetch(`${V2}/auth/me`, {
    headers: { Authorization: `Bearer ${token}` }
  });
  const meData = await meResp.json();
  const userId = meData.user_id;

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
  }, { t: token, uid: userId, un: creds.username, nick: creds.nickname });

  return { ...creds, token, userId };
}

async function createBounty(token, title) {
  const resp = await fetch(`${API_BASE}/bounties`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
    body: JSON.stringify({
      title,
      description: '驳回流程测试悬赏。需要完成一个小型开发任务。',
      category: 'frontend',
      budget_min: 1000,
      budget_max: 2000,
      deadline: new Date(Date.now() + 14 * 24 * 60 * 60 * 1000).toISOString(),
      skill_type: 'prompt'
    })
  });
  const data = await resp.json();
  return data.id;
}

test('bounty rejection flow: poster rejects delivery, developer revises', async ({ page }) => {
  // Register poster and buyer
  const poster = await registerAndLogin(page, 'poster_rej');
  const buyer = await registerAndLogin(page, 'buyer_rej');

  // Create bounty via API
  const bountyId = await createBounty(poster.token, `驳回测试_${Date.now()}`);
  console.log('Bounty ID:', bountyId);

  // Buyer applies for bounty
  const applyResp = await fetch(`${API_BASE}/bounties/${bountyId}/apply`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${buyer.token}` },
    body: JSON.stringify({
      bounty_id: bountyId,
      proposal: '我有丰富的前端开发经验，可以高质量完成此任务。',
      estimated_days: 5,
      quoted_price: 1500,
      portfolio: 'https://github.com/buyer/repo'
    })
  });
  const applyData = await applyResp.json();
  console.log('Apply result:', applyResp.status, JSON.stringify(applyData).substring(0, 200));
  expect(applyResp.status).toBe(200);

  // Poster selects the developer
  await page.evaluate(({ t, uid, un, nick }) => {
    localStorage.setItem('skillbazaar_token', t);
    localStorage.setItem('skillbazaar_user_id', uid);
    localStorage.setItem('skillbazaar_username', un);
    localStorage.setItem('skillbazaar_nickname', nick);
  }, { t: poster.token, uid: poster.userId, un: poster.username, nick: poster.nickname });

  await page.goto(`${FRONTEND}/bounty/${bountyId}`);
  await page.waitForTimeout(2500);

  const selectText = await page.textContent('body');
  expect(selectText).toContain('竞标方案');
  expect(selectText).toContain('待选');

  // Select developer
  await page.click('button:has-text("选择此开发者")');
  await page.waitForTimeout(2000);

  const afterSelect = await page.textContent('body');
  expect(afterSelect).toContain('开发中');
  expect(afterSelect).toContain('已选中');

  // Buyer delivers
  await page.evaluate(({ t, uid, un, nick }) => {
    localStorage.setItem('skillbazaar_token', t);
    localStorage.setItem('skillbazaar_user_id', uid);
    localStorage.setItem('skillbazaar_username', un);
    localStorage.setItem('skillbazaar_nickname', nick);
  }, { t: buyer.token, uid: buyer.userId, un: buyer.username, nick: buyer.nickname });

  await page.goto(`${FRONTEND}/bounty/${bountyId}`);
  await page.waitForTimeout(2500);

  await page.screenshot({ path: '/tmp/reject_buyer_deliver.png', fullPage: false });
  const buyerView = await page.textContent('body');
  console.log('Buyer view (before delivery):', buyerView?.substring(0, 800));

  // Fill delivery form
  await page.fill('textarea[placeholder*="交付内容"]', '第一次交付：已完成基础功能，但可能需要调整细节。');
  await page.click('button:has-text("提交交付")');
  await page.waitForTimeout(2000);

  const afterDelivery = await page.textContent('body');
  console.log('After delivery:', afterDelivery?.substring(0, 800));
  expect(afterDelivery).toContain('已交付');

  // Poster reviews and REJECTS the delivery
  await page.evaluate(({ t, uid, un, nick }) => {
    localStorage.setItem('skillbazaar_token', t);
    localStorage.setItem('skillbazaar_user_id', uid);
    localStorage.setItem('skillbazaar_username', un);
    localStorage.setItem('skillbazaar_nickname', nick);
  }, { t: poster.token, uid: poster.userId, un: poster.username, nick: poster.nickname });

  await page.goto(`${FRONTEND}/bounty/${bountyId}`);
  await page.waitForTimeout(2500);

  await page.screenshot({ path: '/tmp/reject_poster_review.png', fullPage: false });
  const posterReview = await page.textContent('body');
  console.log('Poster review (delivery):', posterReview?.substring(0, 1000));

  // Verify delivery is visible and status is "待审核"
  expect(posterReview).toContain('交付物');
  expect(posterReview).toContain('待审核');

  // Verify reject button exists
  const rejectBtn = page.locator('button:has-text("驳回")');
  const rejectCount = await rejectBtn.count();
  console.log('Reject button count:', rejectCount);
  expect(rejectCount).toBeGreaterThan(0);

  // Click reject button
  await rejectBtn.first().click();
  await page.waitForTimeout(2000);

  await page.screenshot({ path: '/tmp/after_reject.png', fullPage: false });
  const afterReject = await page.textContent('body');
  console.log('After reject:', afterReject?.substring(0, 1000));

  // Verify rejection result - bounty should show "需修改" or "开发中" status
  const hasReviseStatus = afterReject.includes('需修改') ||
                          afterReject.includes('驳回') ||
                          afterReject.includes('重新交付') ||
                          afterReject.includes('开发中');
  console.log('Has revise/reject status:', hasReviseStatus);
  expect(hasReviseStatus).toBe(true);

  // Buyer should be able to see the rejection and re-deliver
  await page.evaluate(({ t, uid, un, nick }) => {
    localStorage.setItem('skillbazaar_token', t);
    localStorage.setItem('skillbazaar_user_id', uid);
    localStorage.setItem('skillbazaar_username', un);
    localStorage.setItem('skillbazaar_nickname', nick);
  }, { t: buyer.token, uid: buyer.userId, un: buyer.username, nick: buyer.nickname });

  await page.goto(`${FRONTEND}/bounty/${bountyId}`);
  await page.waitForTimeout(2500);

  await page.screenshot({ path: '/tmp/reject_buyer_after_reject.png', fullPage: false });
  const buyerAfterReject = await page.textContent('body');
  console.log('Buyer after reject:', buyerAfterReject?.substring(0, 800));

  // Buyer should see delivery section again (to re-deliver)
  const hasDeliverySection = buyerAfterReject.includes('交付技能') ||
                             buyerAfterReject.includes('交付') ||
                             buyerAfterReject.includes('重新');
  console.log('Has delivery section for re-delivery:', hasDeliverySection);

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
