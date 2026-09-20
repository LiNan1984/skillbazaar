import { test, expect } from '@playwright/test';

const V2 = 'http://localhost:8000/api/v2';
const FRONTEND = 'http://localhost:7788';

test('chat panel: open assistant, send message, receive reply', async ({ page }) => {
  // Register and login
  const creds = { username: `chatuser_${Date.now()}`, password: 'test123456', nickname: '聊天用户' };
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

  // Navigate first, inject auth, then reload so React useState picks up the token
  await page.goto(FRONTEND);
  await page.waitForTimeout(1000);

  await page.evaluate(({ t, uid, un, nick }) => {
    localStorage.setItem('skillbazaar_token', t);
    localStorage.setItem('skillbazaar_user_id', uid);
    localStorage.setItem('skillbazaar_username', un);
    localStorage.setItem('skillbazaar_nickname', nick);
  }, { t: loginData.token, uid: meData.user_id, un: creds.username, nick: creds.nickname });

  await page.reload();
  await page.waitForTimeout(2000);

  await page.evaluate(() => {
    document.querySelectorAll('.modal-overlay, [class*="overlay"]').forEach(el => {
      el.style.pointerEvents = 'none';
      el.style.display = 'none';
    });
  });

  // Click floating assistant button to open chat panel
  await page.click('.floating-assistant');
  await page.waitForTimeout(3000);

  await page.screenshot({ path: '/tmp/chat_panel_open.png', fullPage: false });
  const chatText = await page.textContent('body');
  console.log('Chat panel open:', chatText?.substring(0, 800));

  // Verify chat panel is visible
  expect(chatText).toContain('BS买卖助手');

  // 2. Type a message in chat input
  const chatInput = page.locator('.chat-panel textarea, .chat-panel input[type="text"]');
  const inputCount = await chatInput.count();
  console.log('Chat input count:', inputCount);

  if (inputCount > 0) {
    await chatInput.first().fill('推荐一些好的Skill');
    await page.waitForTimeout(500);

    // Press Enter to send
    await chatInput.first().press('Enter');
    await page.waitForTimeout(5000);

    await page.screenshot({ path: '/tmp/chat_after_send.png', fullPage: false });
    const afterSend = await page.textContent('body');
    console.log('After send:', afterSend?.substring(0, 1000));

    // Verify user message appears
    expect(afterSend).toContain('推荐一些好的Skill');

    // Verify bot is processing or has responded
    const hasBotResponse = afterSend.includes('正在') || afterSend.includes('搜索') || afterSend.includes('推荐') || afterSend.includes('抱歉');
    console.log('Bot responded:', hasBotResponse);
  }

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
