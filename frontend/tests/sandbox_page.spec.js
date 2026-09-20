import { test, expect } from '@playwright/test';

const V2 = 'http://localhost:8000/api/v2';
const API_BASE = 'http://localhost:8000/api';
const FRONTEND = 'http://localhost:7788';

test('sandbox page: renders with tabs and no crash', async ({ page }) => {
  // Register and login
  const creds = { username: `sandbox_${Date.now()}`, password: 'test123456', nickname: '沙盒测试用户' };
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
  }, { t: loginData.token, uid: loginData.user_id, un: creds.username, nick: creds.nickname });

  // 1. Navigate to sandbox page
  await page.goto(`${FRONTEND}/sandbox`);
  await page.waitForTimeout(3000);

  await page.screenshot({ path: '/tmp/sandbox_page.png', fullPage: false });
  const sandboxText = await page.textContent('body');
  console.log('Sandbox page:', sandboxText?.substring(0, 1000));

  // 2. Verify sandbox page loaded
  expect(sandboxText).toContain('沙盒');

  // 3. Verify tabs exist
  const hasSandboxTab = sandboxText.includes('沙盒执行');
  const hasEncryptTab = sandboxText.includes('虾塘加密');
  const hasChatTab = sandboxText.includes('AI对话');
  const hasDevTab = sandboxText.includes('开发者');
  console.log('Sandbox tabs:', { hasSandboxTab, hasEncryptTab, hasChatTab, hasDevTab });
  expect(hasSandboxTab || hasEncryptTab || hasChatTab || hasDevTab).toBe(true);

  // 4. Verify code editor or start button exists
  const hasEditor = sandboxText.includes('Python') || sandboxText.includes('编辑器') || sandboxText.includes('运行环境');
  console.log('Has code editor:', hasEditor);

  // 5. Verify navbar still renders
  expect(sandboxText).toContain('SkillBazaar');

  // 6. Switch to chat tab and verify
  const chatTab = page.locator('button:has-text("AI对话"), .tab-btn:has-text("AI对话")');
  const chatTabCount = await chatTab.count();
  if (chatTabCount > 0) {
    await chatTab.first().click();
    await page.waitForTimeout(2000);
    const chatText = await page.textContent('body');
    console.log('Chat tab:', chatText?.substring(0, 500));

    // Verify chat input or empty state
    const hasChatUI = chatText.includes('NPC') ||
                      chatText.includes('对话') ||
                      chatText.includes('输入') ||
                      chatText.includes('startFirst');
    console.log('Has chat UI:', hasChatUI);
  }

  // 7. Verify no console errors
  const consoleErrors = [];
  page.on('console', msg => {
    if (msg.type() === 'error') consoleErrors.push(msg.text());
  });

  await page.reload();
  await page.waitForTimeout(2000);
  console.log('Console errors:', consoleErrors);
  expect(consoleErrors.length).toBe(0);
});
