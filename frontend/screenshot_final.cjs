/**
 * Professional 4:3 screenshots for SkillBazaar
 * 1440x1080 resolution, clean captures
 */
const { chromium } = require('playwright');

(async () => {
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({
    viewport: { width: 1440, height: 1080 },
    deviceScaleFactor: 2, // Retina quality
    locale: 'zh-CN',
  });

  const BASE = 'https://skillbazaar.harness-agent.app';
  const OUT = '/root/skillbazaar/screenshots';

  // Helper: wait for content + screenshot
  async function shot(page, name, opts = {}) {
    await page.waitForTimeout(2000); // let animations settle
    if (opts.scrollTo) {
      await page.evaluate(opts.scrollTo);
      await page.waitForTimeout(1000);
    }
    if (opts.click) {
      for (const sel of opts.click) {
        await page.click(sel).catch(() => {});
        await page.waitForTimeout(500);
      }
    }
    await page.screenshot({ path: `${OUT}/${name}`, fullPage: opts.fullPage || false });
    console.log(`✓ ${name}`);
  }

  // ========== Screenshot 1: Homepage with products ==========
  const p1 = await context.newPage();
  await p1.goto(BASE);
  await p1.waitForSelector('text=190 个商品');
  // Scroll to product grid area
  await p1.evaluate(() => window.scrollTo({ top: 600, behavior: 'smooth' }));
  await p1.waitForTimeout(1500);
  await p1.screenshot({ path: `${OUT}/01_homepage_products.png` });
  console.log('✓ 01_homepage_products.png');

  // ========== Screenshot 2: Bounty market ==========
  const p2 = await context.newPage();
  await p2.goto(BASE);
  await p2.waitForSelector('text=悬赏市场');
  await p2.click('button:has-text("悬赏市场")');
  await p2.waitForTimeout(2000);
  await p2.waitForSelector('text=悬赏');
  await p2.screenshot({ path: `${OUT}/02_bounty_market.png` });
  console.log('✓ 02_bounty_market.png');

  // ========== Screenshot 3: My Library (need login) ==========
  const p3 = await context.newPage();
  await p3.goto(BASE);
  // Login as quant_alice
  await p3.click('button:has-text("登录")');
  await p3.waitForTimeout(1000);
  // Fill login form
  await p3.fill('input[placeholder*="用户名"], input[type="text"]', 'quant_alice').catch(() => {});
  await p3.fill('input[placeholder*="密码"], input[type="password"]', 'npc2024quant').catch(() => {});
  // Click login submit
  await p3.click('button:has-text("登录"):not(:has-text("注册"))').catch(() => {});
  await p3.waitForTimeout(2000);
  
  // Try to navigate to My Library
  await p3.click('button:has-text("我的库")').catch(() => {});
  await p3.waitForTimeout(2000);
  await p3.screenshot({ path: `${OUT}/03_my_library.png` });
  console.log('✓ 03_my_library.png');

  // ========== Screenshot 4: Chat with BS导购助手 ==========
  const p4 = await context.newPage();
  await p4.goto(BASE);
  await p4.waitForSelector('text=BS买卖助手');
  // Find and click the chat toggle/BS assistant
  await p4.click('text=BS买卖助手').catch(() => {});
  await p4.waitForTimeout(1500);
  // Type a query in the chat input
  const chatInput = await p4.$('textarea, input[type="text"][placeholder*="消息"], input[type="text"][placeholder*="输入"]');
  if (chatInput) {
    await chatInput.fill('我想找一个量化交易策略的Agent，预算500以内');
    await p4.waitForTimeout(500);
    // Click send or press Enter
    await p4.keyboard.press('Enter').catch(() => {});
    await p4.click('button:has-text("发送")').catch(() => {});
    // Wait for response
    await p4.waitForTimeout(5000);
  }
  await p4.screenshot({ path: `${OUT}/04_chat_assistant.png` });
  console.log('✓ 04_chat_assistant.png');

  // ========== Screenshot 5: Cron Shop ==========
  const p5 = await context.newPage();
  await p5.goto(`${BASE}/cron-shop`).catch(async () => {
    // Maybe it's a different route
    await p5.goto(BASE);
  });
  await p5.waitForTimeout(2000);
  // Try clicking Cron tab/category
  await p5.click('button:has-text("⏰ Cron")').catch(() => {});
  await p5.waitForTimeout(1500);
  await p5.evaluate(() => window.scrollTo({ top: 400, behavior: 'smooth' }));
  await p5.waitForTimeout(1000);
  await p5.screenshot({ path: `${OUT}/05_cron_shop.png` });
  console.log('✓ 05_cron_shop.png');

  await browser.close();
  console.log('\nAll screenshots done!');
})();
