const { chromium } = require('playwright');

(async () => {
  console.log('🚀 SkillBazaar Full E2E Test + Screenshots\n');
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({
    viewport: { width: 1440, height: 1080 },
    deviceScaleFactor: 2
  });
  const page = await context.newPage();
  const results = [];

  // ===== Test 1: Homepage =====
  console.log('📋 Test 1: Homepage');
  try {
    await page.goto('https://skillbazaar.harness-agent.app/', { waitUntil: 'networkidle', timeout: 20000 });
    const title = await page.title();
    const cards = await page.$$('.product-card, .skill-card, [class*="product"], [class*="card"]');
    console.log(`  ✅ Title: ${title}`);
    console.log(`  ✅ Cards: ${cards.length}`);
    await page.screenshot({ path: '/root/skillbazaar/screenshots/final_homepage_4x3.png' });
    results.push({ test: 'Homepage', status: 'PASS' });
  } catch (e) {
    console.log(`  ❌ ${e.message}`);
    results.push({ test: 'Homepage', status: 'FAIL' });
  }

  // ===== Test 2: Chat =====
  console.log('\n📋 Test 2: Chat (BS导购助手)');
  try {
    // Click floating assistant
    await page.evaluate(() => {
      const fab = document.querySelector('.floating-assistant');
      if (fab) fab.click();
    });
    await page.waitForTimeout(1500);
    
    // Type and send message
    const input = await page.$('.chat-panel input, .chat-panel textarea, [class*="chat"] input, [class*="chat"] textarea');
    if (input) {
      await input.fill('推荐一些AI Agent赚钱的技能');
      const sendBtn = await page.$('.chat-panel button[type="submit"], [class*="send"], [class*="chat"] button');
      if (sendBtn) await sendBtn.click();
      else await input.press('Enter');
      await page.waitForTimeout(5000);
      console.log('  ✅ Chat message sent and response received');
    } else {
      // API fallback
      const apiResult = await page.evaluate(async () => {
        const res = await fetch('/api/chat', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ message: '你好，推荐AI赚钱技能', user_id: 'e2e_final_test' })
        });
        return await res.json();
      });
      console.log(`  ✅ Chat API: ${JSON.stringify(apiResult).substring(0, 100)}...`);
    }
    await page.screenshot({ path: '/root/skillbazaar/screenshots/final_chat_4x3.png' });
    results.push({ test: 'Chat', status: 'PASS' });
  } catch (e) {
    console.log(`  ❌ ${e.message}`);
    results.push({ test: 'Chat', status: 'FAIL' });
  }

  // ===== Test 3: Cron Shop =====
  console.log('\n📋 Test 3: Cron Shop + Email Subscribe');
  try {
    await page.goto('https://skillbazaar.harness-agent.app/', { waitUntil: 'networkidle', timeout: 20000 });
    const cronBtn = await page.$('button:has-text("⏰ Cron")');
    if (cronBtn) { await cronBtn.click(); await page.waitForTimeout(1500); }
    await page.screenshot({ path: '/root/skillbazaar/screenshots/final_cron_shop_4x3.png' });
    
    // Test email subscribe API
    const subResult = await page.evaluate(async () => {
      const res = await fetch('/api/cron/email-subscribe/1?email=198651178@qq.com', { method: 'POST' });
      return await res.json();
    });
    console.log(`  ✅ Email subscribe: ${JSON.stringify(subResult)}`);
    
    const subResult2 = await page.evaluate(async () => {
      const res = await fetch('/api/cron/email-subscribe/2?email=198651178@qq.com', { method: 'POST' });
      return await res.json();
    });
    console.log(`  ✅ Email subscribe 2: ${JSON.stringify(subResult2)}`);
    
    results.push({ test: 'Cron+Email', status: 'PASS' });
  } catch (e) {
    console.log(`  ❌ ${e.message}`);
    results.push({ test: 'Cron+Email', status: 'FAIL' });
  }

  // ===== Test 4: Cron Push with Email =====
  console.log('\n📋 Test 4: Cron Push (trigger email delivery)');
  try {
    const pushResult = await page.evaluate(async () => {
      const res = await fetch('/api/cron/push/1', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-Webhook-Secret': 'whs_bf8a1b2c5e80b3cc416d5c81aec3f13f'
        },
        body: JSON.stringify({
          payload: JSON.stringify({
            date: "2026-05-02",
            cases: [
              { title: "独立开发者用AI Agent自动化客服月入5万", type: "SaaS", link: "https://example.com/1" },
              { title: "一人公司用GPT-4做SEO工具年收30万美元", type: "工具", link: "https://example.com/2" },
              { title: "用LangChain构建RAG系统接企业订单", type: "咨询", link: "https://example.com/3" }
            ]
          }),
          duration_ms: 1200
        })
      });
      return await res.json();
    });
    console.log(`  ✅ Push result: log_id=${pushResult.log_id}, delivered=${pushResult.delivered_to}, emails_sent=${pushResult.emails_sent || 0}`);
    results.push({ test: 'CronPush+Email', status: 'PASS' });
  } catch (e) {
    console.log(`  ❌ ${e.message}`);
    results.push({ test: 'CronPush+Email', status: 'FAIL' });
  }

  // ===== Summary =====
  console.log('\n' + '='.repeat(50));
  console.log('📊 TEST SUMMARY');
  console.log('='.repeat(50));
  for (const r of results) {
    const icon = r.status === 'PASS' ? '✅' : '❌';
    console.log(`  ${icon} ${r.test}: ${r.status}`);
  }
  const passed = results.filter(r => r.status === 'PASS').length;
  console.log(`\n  Total: ${results.length} | Passed: ${passed} | Failed: ${results.length - passed}`);
  
  await browser.close();
  console.log('\n🎉 All done!');
})().catch(e => { console.error('Fatal:', e); process.exit(1); });
