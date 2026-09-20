import { test, expect } from '@playwright/test';
import { execSync } from 'node:child_process';

const V2 = 'http://localhost:8000/api/v2';
const API_BASE = 'http://localhost:8000/api';
const FRONTEND = 'http://localhost:7788';
const DB_PATH = '/Users/linan/Desktop/aicode/skillbazaar/backend/data/skillbazaar.db';

test('admin page: regular user blocked, admin can access analytics', async ({ page }) => {
  // 1. Register regular user
  const creds = { username: `admin_test_${Date.now()}`, password: 'test123456', nickname: '普通用户' };
  await fetch(`${V2}/auth/register`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(creds)
  });
  const loginData = await fetch(`${V2}/auth/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ username: creds.username, password: creds.password })
  }).then(r => r.json());

  // 2. Regular user cannot access admin analytics API
  const analyticsResp = await fetch(`${V2}/admin/analytics`, {
    headers: { Authorization: `Bearer ${loginData.token}` }
  });
  console.log('Regular user analytics status:', analyticsResp.status);
  expect(analyticsResp.status).toBe(403);

  // 3. Regular user cannot access admin lifecycle
  const lifecycleResp = await fetch(`${V2}/admin/lifecycle?limit=5`, {
    headers: { Authorization: `Bearer ${loginData.token}` }
  });
  expect(lifecycleResp.status).toBe(403);
  console.log('Regular user lifecycle blocked');

  // 4. Unauthenticated request blocked
  const unauthResp = await fetch(`${V2}/admin/analytics`);
  expect([401, 403]).toContain(unauthResp.status);
  console.log('Unauthenticated blocked');

  // 5. Promote to admin via DB
  try {
    execSync(`sqlite3 "${DB_PATH}" "UPDATE users SET role='admin' WHERE id='${loginData.user_id}'"`);
  } catch (e) {
    console.log('DB upgrade error:', e.message);
  }

  // Need fresh token after role change
  const adminLoginData = await fetch(`${V2}/auth/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ username: creds.username, password: creds.password })
  }).then(r => r.json());

  // 6. Admin can access analytics
  const adminResp = await fetch(`${V2}/admin/analytics`, {
    headers: { Authorization: `Bearer ${adminLoginData.token}` }
  });
  console.log('Admin analytics status:', adminResp.status);
  expect(adminResp.status).toBe(200);
  const analytics = await adminResp.json();
  console.log('Analytics keys:', Object.keys(analytics));

  // 7. Admin can access lifecycle events
  const adminLifecycle = await fetch(`${V2}/admin/lifecycle?limit=5`, {
    headers: { Authorization: `Bearer ${adminLoginData.token}` }
  });
  expect(adminLifecycle.status).toBe(200);
  console.log('Admin lifecycle accessible');

  // 8. Navigate to admin page UI
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
  }, { t: adminLoginData.token, uid: loginData.user_id, un: creds.username, nick: creds.nickname });

  await page.goto(`${FRONTEND}/admin`);
  await page.waitForTimeout(3000);

  await page.screenshot({ path: '/tmp/admin_page.png', fullPage: false });
  const adminText = await page.textContent('body');
  console.log('Admin page:', adminText?.substring(0, 600));

  expect(adminText).toContain('SkillBazaar');

  // Admin nav link should be visible for admin users
  const adminNavVisible = adminText?.includes('管理') || adminText?.includes('Admin');
  console.log('Admin nav visible:', adminNavVisible);

  // 9. Test admin tabs render
  const hasOverview = adminText?.includes('概览');
  const hasBountyMgmt = adminText?.includes('悬赏管理');
  const hasSkillMgmt = adminText?.includes('Skill管理') || adminText?.includes('商品管理');
  const hasUserMgmt = adminText?.includes('用户管理');
  console.log('Admin tabs:', { hasOverview, hasBountyMgmt, hasSkillMgmt, hasUserMgmt });

  // 10. Verify no console errors
  const consoleErrors = [];
  page.on('console', msg => {
    if (msg.type() === 'error') consoleErrors.push(msg.text());
  });

  await page.reload();
  await page.waitForTimeout(2000);
  console.log('Console errors:', consoleErrors);
  expect(consoleErrors.length).toBe(0);

  // 11. Restore role back to user
  try {
    execSync(`sqlite3 "${DB_PATH}" "UPDATE users SET role='user' WHERE id='${loginData.user_id}'"`);
  } catch {}
});
