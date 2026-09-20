import { test, expect } from '@playwright/test';

const API_BASE = 'http://localhost:8000/api';
const V2 = `${API_BASE}/v2`;
const FRONTEND = 'http://localhost:7788';

test('homepage category filter and product detail navigation', async ({ page }) => {
  // Register and login
  const creds = { username: `catnav_${Date.now()}`, password: 'test123456', nickname: '分类导航' };
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

  // 1. Navigate to homepage
  await page.goto(`${FRONTEND}/`);
  await page.waitForTimeout(3000);

  await page.screenshot({ path: '/tmp/cat_default.png', fullPage: false });
  const defaultText = await page.textContent('body');
  console.log('Homepage default:', defaultText?.substring(0, 300));

  expect(defaultText).toContain('SkillBazaar');
  expect(defaultText).toContain('共');
  expect(defaultText).toContain('个商品');

  // 2. Click "Skill" category tab
  await page.click('button:has-text("Skill")');
  await page.waitForTimeout(2000);

  await page.screenshot({ path: '/tmp/cat_skill.png', fullPage: false });
  const skillText = await page.textContent('body');
  console.log('Skill category:', skillText?.substring(0, 400));

  // Should show Skill products
  const skillCount = await page.locator('.product-card').count();
  console.log('Skill products count:', skillCount);
  expect(skillCount).toBeGreaterThan(0);

  // 3. Click "Agent" category tab
  await page.click('button:has-text("Agent")');
  await page.waitForTimeout(2000);

  await page.screenshot({ path: '/tmp/cat_agent.png', fullPage: false });
  const agentText = await page.textContent('body');
  console.log('Agent category:', agentText?.substring(0, 300));

  // Should show Agent products
  const agentCount = await page.locator('.product-card').count();
  console.log('Agent products count:', agentCount);
  expect(agentCount).toBeGreaterThan(0);

  // 4. Click on a product card to navigate to detail page
  const firstCard = page.locator('.product-card').first();

  await firstCard.click();
  await page.waitForTimeout(3000);

  await page.screenshot({ path: '/tmp/cat_product_detail.png', fullPage: false });
  const detailUrl = page.url();
  console.log('Navigated to:', detailUrl);

  // Should be on product detail page
  expect(detailUrl).toContain('/product/');

  const detailPageText = await page.textContent('body');
  console.log('Product detail:', detailPageText?.substring(0, 500));

  expect(detailPageText).toContain('SkillBazaar');

  // 5. Verify product detail has key sections
  const hasDescription = detailPageText.includes('商品描述') || detailPageText.includes('技能介绍');
  expect(hasDescription).toBe(true);

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
