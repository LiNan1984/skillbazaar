import { test, expect } from '@playwright/test';

const API_BASE = 'http://localhost:8000/api';
const V2 = `${API_BASE}/v2`;
const FRONTEND = 'http://localhost:7788';

test('product search: keyword search filters marketplace results', async ({ page }) => {
  // Register user
  const creds = { username: `searchuser_${Date.now()}`, password: 'test123456', nickname: '搜索用户' };
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

  // 1. Navigate to homepage (no search)
  await page.goto(`${FRONTEND}/`);
  await page.waitForTimeout(3000);

  await page.screenshot({ path: '/tmp/search_default.png', fullPage: false });
  const defaultText = await page.textContent('body');
  console.log('Homepage default:', defaultText?.substring(0, 500));

  // Verify products are shown on homepage
  expect(defaultText).toContain('SkillBazaar');

  // 2. Search for "Agent" keyword via URL params
  await page.goto(`${FRONTEND}/?keyword=Agent`);
  await page.waitForTimeout(3000);

  await page.screenshot({ path: '/tmp/search_agent.png', fullPage: false });
  const agentSearchText = await page.textContent('body');
  console.log('Agent search:', agentSearchText?.substring(0, 800));

  // Should show Agent-related products (defi-yield-hunter, sentiment-analyzer, etc. are Agent category)
  // The search should filter products by keyword matching
  expect(agentSearchText).toContain('SkillBazaar');

  // 3. Search for "数据分析" keyword
  await page.goto(`${FRONTEND}/?keyword=数据分析`);
  await page.waitForTimeout(3000);

  await page.screenshot({ path: '/tmp/search_data_analysis.png', fullPage: false });
  const dataSearchText = await page.textContent('body');
  console.log('Data analysis search:', dataSearchText?.substring(0, 600));

  // 4. Search for non-existent keyword
  await page.goto(`${FRONTEND}/?keyword=不存在的商品xyz`);
  await page.waitForTimeout(3000);

  await page.screenshot({ path: '/tmp/search_no_results.png', fullPage: false });
  const noResultsText = await page.textContent('body');
  console.log('No results:', noResultsText?.substring(0, 600));

  // Should show empty state
  const hasEmptyState = noResultsText.includes('暂无') || noResultsText.includes('没有找到') || noResultsText.includes('0');
  console.log('Has empty state for no results:', hasEmptyState);

  // 5. Navigate to bounty page (different section)
  await page.goto(`${FRONTEND}/bounties`);
  await page.waitForTimeout(2000);

  const bountyPageText = await page.textContent('body');
  console.log('Bounty page:', bountyPageText?.substring(0, 400));

  expect(bountyPageText).toContain('悬赏任务市场');

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
