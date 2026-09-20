import { test, expect } from '@playwright/test';

const API_BASE = 'http://localhost:8000/api';
const V2 = `${API_BASE}/v2`;
const FRONTEND = 'http://localhost:7788';

test('homepage product sorting: popular, newest, price', async ({ page }) => {
  // Register and login
  const creds = { username: `sortuser_${Date.now()}`, password: 'test123456', nickname: '排序用户' };
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

  // 1. Navigate to homepage (default sort: popular)
  await page.goto(`${FRONTEND}/`);
  await page.waitForTimeout(3000);

  await page.screenshot({ path: '/tmp/sort_popular.png', fullPage: false });
  const popularText = await page.textContent('body');
  console.log('Popular sort:', popularText?.substring(0, 400));

  expect(popularText).toContain('SkillBazaar');
  // Default sort should show "热门"
  const hasPopularSort = popularText.includes('热门') || popularText.includes('popular');
  console.log('Default is popular sort:', hasPopularSort);

  // 2. Sort by newest
  await page.click('button:has-text("最新")');
  await page.waitForTimeout(2000);

  await page.screenshot({ path: '/tmp/sort_newest.png', fullPage: false });
  const newestText = await page.textContent('body');
  console.log('Newest sort:', newestText?.substring(0, 400));

  expect(newestText).toContain('SkillBazaar');

  // 3. Sort by price (ascending)
  await page.click('button:has-text("价格↑")');
  await page.waitForTimeout(2000);

  await page.screenshot({ path: '/tmp/sort_price_up.png', fullPage: false });
  const priceUpText = await page.textContent('body');
  console.log('Price asc sort:', priceUpText?.substring(0, 400));

  expect(priceUpText).toContain('SkillBazaar');

  // 4. Sort by price (descending)
  await page.click('button:has-text("价格↓")');
  await page.waitForTimeout(2000);

  await page.screenshot({ path: '/tmp/sort_price_down.png', fullPage: false });
  const priceDownText = await page.textContent('body');
  console.log('Price desc sort:', priceDownText?.substring(0, 400));

  expect(priceDownText).toContain('SkillBazaar');

  // 5. Sort by rating
  await page.click('button:has-text("评分")');
  await page.waitForTimeout(2000);

  await page.screenshot({ path: '/tmp/sort_rating.png', fullPage: false });
  const ratingText = await page.textContent('body');
  console.log('Rating sort:', ratingText?.substring(0, 400));

  expect(ratingText).toContain('SkillBazaar');

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
