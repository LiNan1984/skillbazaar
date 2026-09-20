import { test, expect } from '@playwright/test';

const V2 = 'http://localhost:8000/api/v2';
const FRONTEND = 'http://localhost:7788';

test('404 page: navigate to non-existent URL shows not found', async ({ page }) => {
  // Register and login
  const creds = { username: `nfuser_${Date.now()}`, password: 'test123456', nickname: '404测试用户' };
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

  // Navigate to a non-existent page
  await page.goto(`${FRONTEND}/this-page-does-not-exist-xyz`);
  await page.waitForTimeout(3000);

  await page.screenshot({ path: '/tmp/404_page.png', fullPage: false });
  const pageText = await page.textContent('body');
  console.log('404 page:', pageText?.substring(0, 800));

  // Verify 404 page content
  const isNotFound = pageText.includes('404') || pageText.includes('页面不存在') || pageText.includes('找不到') || pageText.includes('Not Found');
  expect(isNotFound).toBe(true);

  // Verify navbar is still present (layout not broken)
  expect(pageText).toContain('SkillBazaar');

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
