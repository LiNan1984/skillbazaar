const { chromium } = require('playwright');

(async () => {
  console.log('📸 SkillBazaar Professional Screenshots\n');
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({
    viewport: { width: 1440, height: 1080 },
    deviceScaleFactor: 2
  });
  const page = await context.newPage();

  // ===== Screenshot 1: Homepage with Push Notification =====
  console.log('1️⃣ Homepage + Push Notification');
  await page.goto('https://skillbazaar.harness-agent.app/', { waitUntil: 'networkidle', timeout: 30000 });
  await page.waitForTimeout(4000); // Wait for push notification to appear
  // Inject a bounty push notification for screenshot
  await page.evaluate(() => {
    const push = document.createElement('div');
    push.className = 'push-notification push-in';
    push.innerHTML = `
      <div class="push-notification-header">
        <span class="push-badge">🏆 新悬赏</span>
        <button class="push-close">✕</button>
      </div>
      <div class="push-notification-body">
        <span class="push-avatar">🤖</span>
        <div class="push-info">
          <div class="push-title">多模态文档理解Agent</div>
          <div class="push-meta">
            <span class="push-budget">¥12,000-35,000</span>
            <span class="push-category-tag">Agent</span>
          </div>
        </div>
      </div>
      <div class="push-notification-footer">
        <span class="push-time">刚刚</span>
        <a class="push-action">立即查看 →</a>
      </div>`;
    document.body.appendChild(push);
  });
  await page.waitForTimeout(800);
  await page.screenshot({ path: '/root/skillbazaar/screenshots/01_homepage_push.png' });
  console.log('  ✅ Saved 01_homepage_push.png');

  // ===== Screenshot 2: Bounty Page =====
  console.log('2️⃣ Bounty Page');
  await page.goto('https://skillbazaar.harness-agent.app/bounties', { waitUntil: 'networkidle', timeout: 30000 });
  await page.waitForTimeout(2000);
  await page.screenshot({ path: '/root/skillbazaar/screenshots/02_bounties.png' });
  console.log('  ✅ Saved 02_bounties.png');

  // ===== Screenshot 3: Chat with BS导购助手 =====
  console.log('3️⃣ Chat - BS导购助手');
  await page.goto('https://skillbazaar.harness-agent.app/', { waitUntil: 'networkidle', timeout: 30000 });
  // Click floating assistant to open chat
  await page.click('.floating-assistant');
  await page.waitForTimeout(1500);
  // Type a message
  const chatInput = await page.$('.chat-panel input, .chat-panel textarea');
  if (chatInput) {
    await chatInput.fill('我想找一个量化交易的Agent，预算5000左右');
    await chatInput.press('Enter');
    await page.waitForTimeout(8000); // Wait for AI response
  }
  await page.screenshot({ path: '/root/skillbazaar/screenshots/03_chat.png' });
  console.log('  ✅ Saved 03_chat.png');

  // ===== Screenshot 4: My Library =====
  console.log('4️⃣ My Library');
  // First login as sbz_official to see library content
  await page.evaluate(() => {
    localStorage.setItem('skillbazaar_user_id', '874cb09d-74bb-4233-abe5-6e77d35bb979');
    localStorage.setItem('skillbazaar_username', 'sbz_official');
    localStorage.setItem('skillbazaar_nickname', 'SkillBazaar官方');
    localStorage.setItem('skillbazaar_token', 'test');
  });
  await page.goto('https://skillbazaar.harness-agent.app/library', { waitUntil: 'networkidle', timeout: 30000 });
  await page.waitForTimeout(2000);
  await page.screenshot({ path: '/root/skillbazaar/screenshots/04_mylibrary.png' });
  console.log('  ✅ Saved 04_mylibrary.png');

  // ===== Screenshot 5: Cron Shop with Email Subscribe =====
  console.log('5️⃣ Cron Shop');
  await page.goto('https://skillbazaar.harness-agent.app/', { waitUntil: 'networkidle', timeout: 30000 });
  // Click cron tab
  const cronTab = await page.$('button:has-text("⏰"), button:has-text("Cron"), [class*="cron"]');
  if (cronTab) {
    await cronTab.click();
    await page.waitForTimeout(1500);
  }
  await page.screenshot({ path: '/root/skillbazaar/screenshots/05_cron_shop.png' });
  console.log('  ✅ Saved 05_cron_shop.png');

  // ===== Screenshot 6: Product Detail (high-quality Agent) =====
  console.log('6️⃣ Product Detail');
  // Find the first Agent product
  const agentProducts = await page.evaluate(async () => {
    const res = await fetch('/api/products?category=Agent&page_size=1');
    const data = await res.json();
    return data.products.map(p => p.id);
  });
  if (agentProducts.length > 0) {
    await page.goto(`https://skillbazaar.harness-agent.app/product/${agentProducts[0]}`, { waitUntil: 'networkidle', timeout: 30000 });
    await page.waitForTimeout(1500);
    await page.screenshot({ path: '/root/skillbazaar/screenshots/06_product_detail.png' });
    console.log('  ✅ Saved 06_product_detail.png');
  }

  // ===== Generate 4:3 final screenshots =====
  console.log('\n🖼️ Generating 4:3 final crops...');
  // The screenshots above are 1440x1080 which is already 4:3 at 2x DPI (2880x2160)
  // They're already 4:3! Just rename the best ones
  
  await browser.close();
  console.log('\n🎉 All screenshots done!');
})().catch(e => { console.error('Fatal:', e); process.exit(1); });
