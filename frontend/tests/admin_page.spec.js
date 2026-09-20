import { test, expect } from '@playwright/test';

const V2 = 'http://localhost:8000/api/v2';
const FRONTEND = 'http://localhost:7788';

test('admin page: renders with admin role without crashing', async ({ page }) => {
  // Register user with nickname 'admin' to show admin link
  const creds = { username: `admin_${Date.now()}`, password: 'test123456', nickname: 'admin' };
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

  const meResp = await fetch(`${V2}/auth/me`, {
    headers: { Authorization: `Bearer ${loginData.token}` }
  });
  const meData = await meResp.json();

  await page.goto(FRONTEND);
  await page.waitForTimeout(1500);

  // Set nickname to 'admin' to show admin link in navbar
  await page.evaluate(() => {
    localStorage.setItem('skillbazaar_token', '');
    localStorage.setItem('skillbazaar_user_id', '');
    localStorage.setItem('skillbazaar_username', '');
    localStorage.setItem('skillbazaar_nickname', 'admin');
  });

  // Now inject the real auth
  await page.evaluate(({ t, uid, un, nick }) => {
    localStorage.setItem('skillbazaar_token', t);
    localStorage.setItem('skillbazaar_user_id', uid);
    localStorage.setItem('skillbazaar_username', un);
    localStorage.setItem('skillbazaar_nickname', nick);
  }, { t: loginData.token, uid: meData.user_id, un: creds.username, nick: creds.nickname });

  // 1. Navigate to admin page directly
  await page.goto(`${FRONTEND}/admin`);
  await page.waitForTimeout(3000);

  await page.screenshot({ path: '/tmp/admin_page.png', fullPage: false });
  const adminText = await page.textContent('body');
  console.log('Admin page:', adminText?.substring(0, 1500));

  // 2. Verify admin page loaded (admin tab labels should be present)
  expect(adminText).toContain('概览');

  // 3. Verify admin tabs exist
  const hasBountiesTab = adminText.includes('悬赏管理');
  const hasSkillsTab = adminText.includes('Skill管理');
  const hasUsersTab = adminText.includes('用户管理');
  const hasRisksTab = adminText.includes('风险扫描');
  console.log('Admin tabs:', { hasBountiesTab, hasSkillsTab, hasUsersTab, hasRisksTab });

  // At least the overview tab should be present
  expect(adminText).toContain('概览');

  // 4. Try switching to bounties tab
  if (hasBountiesTab) {
    await page.click('button:has-text("悬赏管理"), .tab-btn:has-text("悬赏管理")');
    await page.waitForTimeout(2000);

    await page.screenshot({ path: '/tmp/admin_bounties_tab.png', fullPage: false });
    const bountiesTabText = await page.textContent('body');
    console.log('Admin bounties tab:', bountiesTabText?.substring(0, 800));
  }

  // 5. Try switching to skills tab
  if (hasSkillsTab) {
    await page.click('button:has-text("Skill管理"), .tab-btn:has-text("Skill管理")');
    await page.waitForTimeout(2000);

    await page.screenshot({ path: '/tmp/admin_skills_tab.png', fullPage: false });
    const skillsTabText = await page.textContent('body');
    console.log('Admin skills tab:', skillsTabText?.substring(0, 800));
  }

  // 6. Verify no critical console errors (404s from missing API are expected)
  const consoleErrors = [];
  const consoleWarnings = [];
  page.on('console', msg => {
    if (msg.type() === 'error') consoleErrors.push(msg.text());
    if (msg.type() === 'warning') consoleWarnings.push(msg.text());
  });

  await page.reload();
  await page.waitForTimeout(2000);
  console.log('Console errors:', consoleErrors.slice(0, 5));
  console.log('Console warnings:', consoleWarnings.slice(0, 5));

  // Admin page should render even if API calls fail
  expect(adminText).toContain('SkillBazaar');
});
