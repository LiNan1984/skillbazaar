/**
 * Final professional 4:3 screenshots (1440x1080, 2x DPI)
 * Login as test_screenshot, capture all key pages
 */
const { chromium } = require('playwright');

(async () => {
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({
    viewport: { width: 1440, height: 1080 },
    deviceScaleFactor: 2,
    locale: 'zh-CN',
  });
  const BASE = 'https://skillbazaar.harness-agent.app';
  const OUT = '/root/skillbazaar/screenshots/final';

  const fs = require('fs');
  fs.mkdirSync(OUT, { recursive: true });

  // ===== Step 1: Login via API, set token in localStorage =====
  const page = await context.newPage();
  
  // First goto to set domain
  await page.goto(BASE);
  await page.waitForTimeout(1000);
  
  // Login via API
  const loginResp = await page.evaluate(async () => {
    const resp = await fetch('/api/v2/auth/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username: 'test_screenshot', password: 'Test2024!' })
    });
    return await resp.json();
  });
  
  console.log('Login response:', JSON.stringify(loginResp).substring(0, 100));
  
  if (loginResp.token) {
    // Store token in localStorage
    await page.evaluate((token) => {
      localStorage.setItem('token', token);
      localStorage.setItem('user', JSON.stringify({
        user_id: '8565c756-1ab5-46d9-8f17-fe87ea947acd',
        username: 'test_screenshot',
        nickname: '截图测试员',
        coins: 999999
      }));
    }, loginResp.token);
    
    // Reload page with auth
    await page.reload();
    await page.waitForTimeout(2000);
    console.log('Auth set, page reloaded');
  }

  // ===== Screenshot 1: Homepage with products =====
  // Scroll down to product grid
  await page.evaluate(() => window.scrollTo({ top: 700, behavior: 'instant' }));
  await page.waitForTimeout(1500);
  await page.screenshot({ path: `${OUT}/01_homepage.png` });
  console.log('✓ 01_homepage.png');

  // ===== Screenshot 2: Bounty Market =====
  // Close any push notification first
  await page.click('button:has-text("✕")').catch(() => {});
  await page.waitForTimeout(500);
  
  await page.click('button:has-text("悬赏市场")').catch(() => {});
  await page.waitForTimeout(3000);
  await page.screenshot({ path: `${OUT}/02_bounty_market.png` });
  console.log('✓ 02_bounty_market.png');

  // ===== Screenshot 3: My Library =====
  await page.goto(BASE);
  await page.waitForTimeout(2000);
  await page.click('button:has-text("✕")').catch(() => {});
  await page.waitForTimeout(500);
  await page.click('button:has-text("我的库")');
  await page.waitForTimeout(3000);
  await page.screenshot({ path: `${OUT}/03_my_library.png` });
  console.log('✓ 03_my_library.png');

  // ===== Screenshot 4: Chat with BS导购助手 =====
  await page.goto(BASE);
  await page.waitForTimeout(2000);
  await page.click('button:has-text("✕")').catch(() => {});
  await page.waitForTimeout(500);
  
  // Find the chat assistant button at bottom right
  const chatToggle = await page.$('button:has-text("BS买卖助手"), div:has-text("BS买卖助手")');
  if (chatToggle) {
    await chatToggle.click().catch(() => {});
    await page.waitForTimeout(1500);
  }
  
  // Type a query in chat
  const chatInput = await page.$('textarea, input[placeholder*="消息"], input[placeholder*="输入"], input[placeholder*="问我"]');
  if (chatInput) {
    await chatInput.fill('我想找一个量化交易策略的Agent，预算500以内');
    await page.waitForTimeout(500);
    await page.keyboard.press('Enter');
    await page.waitForTimeout(8000);
  }
  await page.screenshot({ path: `${OUT}/04_chat_assistant.png` });
  console.log('✓ 04_chat_assistant.png');

  // ===== Screenshot 5: Cron Shop (click Cron tab) =====
  await page.goto(BASE);
  await page.waitForTimeout(2000);
  await page.click('button:has-text("✕")').catch(() => {});
  await page.waitForTimeout(500);
  await page.evaluate(() => window.scrollTo({ top: 700, behavior: 'instant' }));
  await page.waitForTimeout(1000);
  await page.click('button:has-text("⏰ Cron")');
  await page.waitForTimeout(2000);
  await page.screenshot({ path: `${OUT}/05_cron_shop.png` });
  console.log('✓ 05_cron_shop.png');

  await browser.close();
  console.log('\nAll final screenshots done!');
})();
