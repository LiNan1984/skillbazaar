const { chromium } = require('playwright');

(async () => {
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({
    viewport: { width: 1440, height: 1080 },  // 4:3
    deviceScaleFactor: 2
  });
  const page = await context.newPage();

  // ========== Screenshot 1: Homepage Hero + Products ==========
  console.log('📸 Screenshot 1: Homepage');
  await page.goto('https://skillbazaar.harness-agent.app/', { waitUntil: 'networkidle', timeout: 20000 });
  await page.waitForTimeout(1000);
  await page.screenshot({ path: '/root/skillbazaar/screenshots/final_homepage_4x3.png' });
  console.log('  Saved: final_homepage_4x3.png');

  // ========== Screenshot 2: Cron Category ==========
  console.log('📸 Screenshot 2: Cron Shop');
  const cronBtn = await page.$('button:has-text("⏰ Cron")');
  if (cronBtn) {
    await cronBtn.click();
    await page.waitForTimeout(1500);
  }
  await page.screenshot({ path: '/root/skillbazaar/screenshots/final_cron_shop_4x3.png' });
  console.log('  Saved: final_cron_shop_4x3.png');

  // ========== Screenshot 3: Chat Panel ==========
  console.log('📸 Screenshot 3: Chat with BS导购助手');
  await page.goto('https://skillbazaar.harness-agent.app/', { waitUntil: 'networkidle', timeout: 20000 });
  
  // Click floating assistant
  const fab = await page.$('.floating-assistant');
  if (fab) {
    await fab.click();
    await page.waitForTimeout(1500);
  }
  
  // Type message
  const chatInput = await page.$('.chat-panel input, .chat-panel textarea, [class*="chat"] input, [class*="chat"] textarea');
  if (chatInput) {
    await chatInput.fill('推荐一些AI Agent赚钱的技能');
    const sendBtn = await page.$('.chat-panel button[type="submit"], [class*="send"], [class*="chat"] button');
    if (sendBtn) await sendBtn.click();
    else await chatInput.press('Enter');
    await page.waitForTimeout(4000);
  }
  await page.screenshot({ path: '/root/skillbazaar/screenshots/final_chat_4x3.png' });
  console.log('  Saved: final_chat_4x3.png');

  // ========== Screenshot 4: Cron Product Detail ==========
  console.log('📸 Screenshot 4: Cron Product - 每日AI盈利案例');
  await page.goto('https://skillbazaar.harness-agent.app/', { waitUntil: 'networkidle', timeout: 20000 });
  // Click Cron category
  const cronTab = await page.$('button:has-text("⏰ Cron")');
  if (cronTab) {
    await cronTab.click();
    await page.waitForTimeout(1500);
  }
  // Click the cron product card
  const cronCards = await page.$$('a[href*="/product/"]');
  for (const card of cronCards) {
    const text = await card.textContent();
    if (text && (text.includes('ai-profit') || text.includes('daily'))) {
      await card.click();
      await page.waitForTimeout(2000);
      break;
    }
  }
  await page.screenshot({ path: '/root/skillbazaar/screenshots/final_cron_detail_4x3.png' });
  console.log('  Saved: final_cron_detail_4x3.png');

  await browser.close();
  console.log('\n✅ All 4:3 screenshots generated!');
})().catch(e => { console.error('Fatal:', e); process.exit(1); });
