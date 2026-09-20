import { test, expect } from '@playwright/test';

const API_BASE = 'http://localhost:8000/api';
const V2 = `${API_BASE}/v2`;
const FRONTEND = 'http://localhost:7788';

test('bounty listing page with filters and search', async ({ page }) => {
  // Register and login
  const creds = { username: `bountylist_${Date.now()}`, password: 'test123456', nickname: '悬赏列表测试' };
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

  // Create a test bounty first
  const createResp = await fetch(`${API_BASE}/bounties`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${loginData.token}` },
    body: JSON.stringify({
      title: `列表测试悬赏_${Date.now()}`,
      description: '测试悬赏列表页面过滤和搜索功能的任务描述。',
      category: 'frontend',
      budget_min: 500,
      budget_max: 1000,
      deadline: new Date(Date.now() + 7 * 24 * 60 * 60 * 1000).toISOString(),
      skill_type: 'prompt'
    })
  });
  const createData = await createResp.json();
  console.log('Created bounty:', createData.id);
  expect(createResp.status).toBe(200);

  // 1. Navigate to bounty page
  await page.goto(`${FRONTEND}/bounties`);
  await page.waitForTimeout(3000);

  await page.screenshot({ path: '/tmp/bounty_list.png', fullPage: false });
  const pageText = await page.textContent('body');
  console.log('Bounty list:', pageText?.substring(0, 800));

  // Verify page title and bounty content
  expect(pageText).toContain('悬赏任务市场');
  expect(pageText).toContain('列表测试悬赏');

  // 2. Verify status filter tabs exist
  expect(pageText).toContain('招募中');
  expect(pageText).toContain('全部');

  // 3. Click "全部" tab to see all bounties
  await page.click('button:has-text("全部")');
  await page.waitForTimeout(2000);

  await page.screenshot({ path: '/tmp/bounty_list_all.png', fullPage: false });
  const allText = await page.textContent('body');
  console.log('All bounties:', allText?.substring(0, 800));

  expect(allText).toContain('列表测试悬赏');

  // 4. Test search functionality
  const searchInput = page.locator('input[placeholder*="搜索悬赏"]');
  await searchInput.fill('列表测试');
  await page.keyboard.press('Enter');
  await page.waitForTimeout(2000);

  await page.screenshot({ path: '/tmp/bounty_search.png', fullPage: false });
  const searchText = await page.textContent('body');
  console.log('Search result:', searchText?.substring(0, 800));

  expect(searchText).toContain('列表测试悬赏');

  // 5. Click on the bounty to view detail page
  await page.click('text=列表测试悬赏');
  await page.waitForTimeout(3000);

  await page.screenshot({ path: '/tmp/bounty_detail_from_list.png', fullPage: false });
  const detailText = await page.textContent('body');
  console.log('Bounty detail:', detailText?.substring(0, 1000));

  // Should be on detail page
  expect(page.url()).toContain('/bounty/');
  expect(detailText).toContain('列表测试悬赏');
  expect(detailText).toContain('测试悬赏列表页面过滤和搜索功能');

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
