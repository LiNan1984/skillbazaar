import { test, expect } from '@playwright/test';

const V2 = 'http://localhost:8000/api/v2';
const API_BASE = 'http://localhost:8000/api';
const FRONTEND = 'http://localhost:7788';

test('library: create and manage personal agents', async ({ page }) => {
  const creds = { username: `libagent_${Date.now()}`, password: 'test123456', nickname: '智能体测试用户' };
  await fetch(`${V2}/auth/register`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(creds)
  });

  const loginResp = await fetch(`${V2}/auth/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ username: creds.username, password: creds.password })
  });
  const loginData = await loginResp.json();

  // 1. Test agents API - list (empty initially)
  const agentsResp = await fetch(`${API_BASE}/agents`, {
    headers: { Authorization: `Bearer ${loginData.token}` }
  });
  console.log('Agents list status:', agentsResp.status);
  const agentsData = await agentsResp.json().catch(() => []);
  const initialAgents = Array.isArray(agentsData) ? agentsData : (agentsData.agents || agentsData.items || []);
  console.log('Initial agents:', initialAgents.length);

  // 2. Create an agent via API
  const createResp = await fetch(`${API_BASE}/agents`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${loginData.token}` },
    body: JSON.stringify({
      name: `E2E智能体_${Date.now()}`,
      description: 'E2E测试创建的智能体',
      system_prompt: '你是一个测试助手',
      skill_ids: []
    })
  });
  const createData = await createResp.json();
  console.log('Create agent:', createResp.status, createData);
  expect([200, 201]).toContain(createResp.status);

  const agentId = createData.id || createData.agent_id;
  expect(agentId).toBeTruthy();

  // 3. Verify agent appears in list
  const agentsResp2 = await fetch(`${API_BASE}/agents`, {
    headers: { Authorization: `Bearer ${loginData.token}` }
  });
  const agentsData2 = await agentsResp2.json();
  const agents2 = Array.isArray(agentsData2) ? agentsData2 : (agentsData2.agents || agentsData2.items || []);
  expect(agents2.length).toBeGreaterThanOrEqual(1);

  const createdAgent = agents2.find(a => a.id === agentId || a.name?.includes('E2E智能体'));
  expect(createdAgent).toBeTruthy();
  console.log('Agent found in list:', createdAgent.name);

  // 4. Navigate to library page
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
  }, { t: loginData.token, uid: loginData.user_id, un: creds.username, nick: creds.nickname });

  await page.goto(`${FRONTEND}/library`);
  await page.waitForTimeout(3000);

  await page.screenshot({ path: '/tmp/library_agents.png', fullPage: false });
  const libText = await page.textContent('body');
  console.log('Library agents tab:', libText?.substring(0, 800));

  // Verify agents tab content
  expect(libText).toContain('我的库');
  expect(libText).toContain('我的智能体');

  // The created agent should appear
  const showsAgent = libText?.includes('E2E智能体');
  console.log('Created agent visible:', showsAgent);

  // 5. Test tab switching
  const skillsTab = page.locator('button:has-text("已购技能")');
  if (await skillsTab.count() > 0) {
    await skillsTab.first().click();
    await page.waitForTimeout(1000);

    const skillsText = await page.textContent('body');
    console.log('Skills tab loaded:', skillsText?.includes('已购技能'));
  }

  const cronsTab = page.locator('button:has-text("Cron订阅")');
  if (await cronsTab.count() > 0) {
    await cronsTab.first().click();
    await page.waitForTimeout(1000);

    const cronsText = await page.textContent('body');
    const cronsEmpty = cronsText?.includes('暂无') || cronsText?.includes('还没有') || cronsText?.includes('订阅');
    console.log('Cron tab renders:', cronsEmpty);
  }

  const bountiesTab = page.locator('button:has-text("悬赏任务")');
  if (await bountiesTab.count() > 0) {
    await bountiesTab.first().click();
    await page.waitForTimeout(1000);

    const bountiesText = await page.textContent('body');
    console.log('Bounty tab renders:', bountiesText?.includes('悬赏'));
  }

  // 6. Delete agent via API
  const deleteResp = await fetch(`${API_BASE}/agents/${agentId}`, {
    method: 'DELETE',
    headers: { Authorization: `Bearer ${loginData.token}` }
  });
  console.log('Delete agent:', deleteResp.status);
  expect([200, 204]).toContain(deleteResp.status);

  // 7. Verify no console errors
  const consoleErrors = [];
  page.on('console', msg => {
    if (msg.type() === 'error') consoleErrors.push(msg.text());
  });

  await page.goto(`${FRONTEND}/library`);
  await page.waitForTimeout(2000);
  console.log('Console errors:', consoleErrors);
  expect(consoleErrors.length).toBe(0);
});
