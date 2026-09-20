import { test, expect } from '@playwright/test';

const API_BASE = 'http://localhost:8000/api';
const V2 = `${API_BASE}/v2`;
const FRONTEND = 'http://localhost:7788';

test('logout and re-login with different user', async ({ page }) => {
  // 1. Register and login as first user
  const creds1 = { username: `logoutuser1_${Date.now()}`, password: 'test123456', nickname: '登录用户A' };
  const regResp1 = await fetch(`${V2}/auth/register`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(creds1)
  });
  await regResp1.json();

  const loginResp1 = await fetch(`${V2}/auth/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ username: creds1.username, password: creds1.password })
  });
  const loginData1 = await loginResp1.json();

  const meResp1 = await fetch(`${V2}/auth/me`, {
    headers: { Authorization: `Bearer ${loginData1.token}` }
  });
  const meData1 = await meResp1.json();

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
  }, { t: loginData1.token, uid: meData1.user_id, un: creds1.username, nick: creds1.nickname });

  // 2. Verify first user is logged in
  await page.goto(FRONTEND);
  await page.waitForTimeout(2000);

  const loggedInText = await page.textContent('body');
  console.log('First user logged in:', loggedInText?.substring(0, 400));
  expect(loggedInText).toContain('登录用户A');
  expect(loggedInText).toContain('10,000');

  // 3. Click logout
  await page.click('button:has-text("退出")');
  await page.waitForTimeout(2000);

  await page.screenshot({ path: '/tmp/after_logout.png', fullPage: false });
  const afterLogoutText = await page.textContent('body');
  console.log('After logout:', afterLogoutText?.substring(0, 400));

  // 4. Verify logout succeeded — first user name gone, login button appears
  expect(afterLogoutText).not.toContain('登录用户A');
  expect(afterLogoutText).toContain('登录');
  // After logout, username should not appear; wallet balance indicator gone
  const hasNoWallet = !afterLogoutText.includes('钱包登录');
  expect(hasNoWallet).toBe(true);

  // 5. Register and login as second user
  const creds2 = { username: `logoutuser2_${Date.now()}`, password: 'test123456', nickname: '登录用户B' };
  const regResp2 = await fetch(`${V2}/auth/register`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(creds2)
  });
  await regResp2.json();

  const loginResp2 = await fetch(`${V2}/auth/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ username: creds2.username, password: creds2.password })
  });
  const loginData2 = await loginResp2.json();

  const meResp2 = await fetch(`${V2}/auth/me`, {
    headers: { Authorization: `Bearer ${loginData2.token}` }
  });
  const meData2 = await meResp2.json();

  await page.evaluate(() => {
    localStorage.setItem('skillbazaar_token', '');
    localStorage.setItem('skillbazaar_user_id', '');
    localStorage.setItem('skillbazaar_username', '');
    localStorage.setItem('skillbazaar_nickname', '');
  });
  await page.evaluate(({ t, uid, un, nick }) => {
    localStorage.setItem('skillbazaar_token', t);
    localStorage.setItem('skillbazaar_user_id', uid);
    localStorage.setItem('skillbazaar_username', un);
    localStorage.setItem('skillbazaar_nickname', nick);
  }, { t: loginData2.token, uid: meData2.user_id, un: creds2.username, nick: creds2.nickname });

  // 6. Reload and verify second user is logged in
  await page.goto(FRONTEND);
  await page.waitForTimeout(2000);

  await page.screenshot({ path: '/tmp/second_user_logged_in.png', fullPage: false });
  const secondUserText = await page.textContent('body');
  console.log('Second user logged in:', secondUserText?.substring(0, 400));

  expect(secondUserText).toContain('登录用户B');
  expect(secondUserText).toContain('10,000');
  expect(secondUserText).not.toContain('登录用户A');

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
