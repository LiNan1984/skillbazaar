import { test, expect } from '@playwright/test';

const API_BASE = 'http://localhost:8000/api';
const V2 = `${API_BASE}/v2`;
const FRONTEND = 'http://localhost:7788';

test('library page: purchase shows in skills tab, tab switching', async ({ page }) => {
  // Register user
  const creds = { username: `libuser_${Date.now()}`, password: 'test123456', nickname: '库用户' };
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

  // Purchase two free products: code-reviewer (id=1) and mcporter (id=106)
  await fetch(`${API_BASE}/transactions/buy`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${loginData.token}` },
    body: JSON.stringify({ product_id: 1, user_id: meData.user_id })
  }).then(r => r.json());

  await fetch(`${API_BASE}/transactions/buy`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${loginData.token}` },
    body: JSON.stringify({ product_id: 106, user_id: meData.user_id })
  }).then(r => r.json());

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
  }, { t: loginData.token, uid: meData.user_id, un: creds.username, nick: creds.nickname });

  // 1. Navigate to library page - defaults to agents tab
  await page.goto(`${FRONTEND}/library`);
  await page.waitForTimeout(3000);

  await page.screenshot({ path: '/tmp/library_default.png', fullPage: false });

  // 2. Switch to "已购技能" tab
  await page.click('button:has-text("已购技能")');
  await page.waitForTimeout(2000);

  await page.screenshot({ path: '/tmp/library_skills.png', fullPage: false });
  const skillsText = await page.textContent('body');
  console.log('Library skills tab:', skillsText?.substring(0, 800));

  // Verify both purchased products appear
  expect(skillsText).toContain('code-reviewer');
  expect(skillsText).toContain('mcporter');
  expect(skillsText).toContain('已购技能');
  expect(skillsText).toContain('已购买');

  // 2. Switch to "我的智能体" tab
  await page.click('button:has-text("我的智能体")');
  await page.waitForTimeout(2000);

  await page.screenshot({ path: '/tmp/library_agents.png', fullPage: false });
  const agentsText = await page.textContent('body');
  console.log('Library agents tab:', agentsText?.substring(0, 400));

  expect(agentsText).toContain('我的智能体');
  // No agents yet, should show empty state
  expect(agentsText).toContain('还没有创建智能体');

  // 3. Switch to "Cron订阅" tab
  await page.click('button:has-text("Cron订阅")');
  await page.waitForTimeout(2000);

  const cronsText = await page.textContent('body');
  console.log('Library crons tab:', cronsText?.substring(0, 400));

  expect(cronsText).toContain('Cron订阅');
  expect(cronsText).toContain('还没有订阅定时任务');

  // 4. Switch to "悬赏任务" tab
  await page.click('button:has-text("悬赏任务")');
  await page.waitForTimeout(2000);

  const bountiesText = await page.textContent('body');
  console.log('Library bounties tab:', bountiesText?.substring(0, 400));

  expect(bountiesText).toContain('悬赏任务');
  expect(bountiesText).toContain('暂无承接的悬赏任务');

  // 5. Go back to skills tab and click on a product
  await page.click('button:has-text("已购技能")');
  await page.waitForTimeout(2000);

  await page.click('.library-card:has-text("code-reviewer")');
  await page.waitForTimeout(3000);

  await page.screenshot({ path: '/tmp/library_click_product.png', fullPage: false });
  const productDetail = await page.textContent('body');
  console.log('Product detail from library:', productDetail?.substring(0, 400));

  expect(page.url()).toContain('/product/1');
  expect(productDetail).toContain('code-reviewer');

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
