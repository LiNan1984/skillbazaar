import { chromium } from 'playwright';

const BASE = 'http://localhost:7788';
const API = 'http://localhost:8000';
const errors = [];
const results = [];

async function main() {
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({ viewport: { width: 1280, height: 900 } });
  const page = await context.newPage();

  page.on('console', msg => {
    if (msg.type() === 'error') errors.push(`CONSOLE ERROR: ${msg.text()}`);
  });
  page.on('pageerror', err => errors.push(`PAGE ERROR: ${err.message}`));

  page.on('response', async (resp) => {
    if (resp.status() >= 400) {
      const url = resp.url();
      try {
        const text = await resp.text();
        errors.push(`RESPONSE ${resp.status()}: ${url} -> ${text.substring(0, 200)}`);
      } catch(e) {
        errors.push(`RESPONSE ${resp.status()}: ${url}`);
      }
    }
  });

  // Register + Login
  console.log('[Setup] Registering user...');
  const uniqueUsername = `action_test_${Date.now()}`;
  const regResp = await page.request.post(`${API}/api/v2/auth/register`, {
    data: { username: uniqueUsername, password: 'TestPass123!', nickname: 'ActionTest' }
  });
  const regData = await regResp.json();
  const username = regData.username || uniqueUsername;

  const loginResp = await page.request.post(`${API}/api/v2/auth/login`, {
    data: { username, password: 'TestPass123!' }
  });
  const loginData = await loginResp.json();
  const token = loginData.token;
  const userId = loginData.user_id;
  console.log(`[Setup] Logged in as ${username}, userId: ${userId}`);

  await page.goto(`${BASE}/login`, { waitUntil: 'networkidle', timeout: 30000 });
  await page.evaluate((data) => {
    localStorage.setItem('skillbazaar_token', data.token);
    localStorage.setItem('skillbazaar_user_id', data.userId);
  }, { token, userId });
  await page.waitForTimeout(1000);

  // ============ TEST 1: Browse and Filter Products ============
  console.log('\n[Test 1] Browse products with filters...');
  await page.goto(`${BASE}/`, { waitUntil: 'networkidle', timeout: 30000 });
  await page.waitForTimeout(2000);

  // Try clicking on a category filter
  const categoryLinks = await page.locator('a[href*="category="], button:has-text("Agent"), button:has-text("Skill")').all();
  if (categoryLinks.length > 0) {
    await categoryLinks[0].click();
    await page.waitForTimeout(2000);
    console.log('  ✓ Clicked category filter');
    results.push('PASS: Category filter works');
  } else {
    console.log('  ! No category filters found');
    results.push('SKIP: No category filters');
  }

  // ============ TEST 2: View Product Details ============
  console.log('\n[Test 2] View product details...');
  const productLinks = await page.locator('a[href*="/product/"]').all();
  if (productLinks.length > 0) {
    await productLinks[0].click();
    await page.waitForTimeout(2000);
    const detailText = await page.textContent('body');
    if (detailText.length > 200) {
      console.log(`  ✓ Product detail loaded (${detailText.length} chars)`);
      results.push('PASS: Product detail page loads');

      // Check for buy button
      const hasBuyButton = detailText.includes('立即购买') || detailText.includes('Buy Now') || detailText.includes('购买');
      if (hasBuyButton) {
        console.log('  ✓ Buy button visible');
        results.push('PASS: Buy button exists');
      }
    }
  } else {
    console.log('  ! No product links found');
    results.push('SKIP: No products to view');
  }

  // ============ TEST 3: Test Chat with BS Assistant ============
  console.log('\n[Test 3] Chat with BS Assistant...');
  await page.goto(`${BASE}/`, { waitUntil: 'networkidle', timeout: 30000 });
  await page.waitForTimeout(2000);

  // Look for chat widget/button
  const chatButton = await page.locator('button:has-text("聊天"), button:has-text("Chat"), [class*="chat"]').first();
  if (await chatButton.count() > 0) {
    await chatButton.click();
    await page.waitForTimeout(1000);
    console.log('  ✓ Chat widget opened');
    results.push('PASS: Chat widget opens');
  } else {
    console.log('  ! No chat widget found');
    results.push('SKIP: No chat widget');
  }

  // ============ TEST 4: Navigate to Library and Check Content ============
  console.log('\n[Test 4] Check library content...');
  await page.goto(`${BASE}/library`, { waitUntil: 'networkidle', timeout: 30000 });
  await page.waitForTimeout(2000);

  const libText = await page.textContent('body');
  if (libText.length > 50) {
    console.log(`  ✓ Library page loaded (${libText.length} chars)`);
    console.log(`  Content preview: ${libText.substring(0, 150)}`);
    results.push('PASS: Library page loads with content');
  } else {
    console.log('  ✗ Library page empty');
    results.push('FAIL: Library page empty');
  }

  // ============ TEST 5: Check Activities Page ============
  console.log('\n[Test 5] Check activities...');
  await page.goto(`${BASE}/activities`, { waitUntil: 'networkidle', timeout: 30000 });
  await page.waitForTimeout(2000);

  const actText = await page.textContent('body');
  if (actText.length > 100) {
    console.log(`  ✓ Activities page loaded (${actText.length} chars)`);
    console.log(`  Preview: ${actText.substring(0, 200)}`);
    results.push('PASS: Activities page loads');
  } else {
    console.log('  ✗ Activities page empty');
    results.push('FAIL: Activities page empty');
  }

  // ============ TEST 6: Check Publish Page ============
  console.log('\n[Test 6] Check publish page...');
  await page.goto(`${BASE}/publish`, { waitUntil: 'networkidle', timeout: 30000 });
  await page.waitForTimeout(2000);

  const pubText = await page.textContent('body');
  if (pubText.length > 100) {
    console.log(`  ✓ Publish page loaded (${pubText.length} chars)`);
    console.log(`  Preview: ${pubText.substring(0, 200)}`);
    results.push('PASS: Publish page loads');
  } else {
    console.log('  ✗ Publish page empty');
    results.push('FAIL: Publish page empty');
  }

  // ============ TEST 7: Check Seller Dashboard ============
  console.log('\n[Test 7] Check seller dashboard...');
  await page.goto(`${BASE}/seller`, { waitUntil: 'networkidle', timeout: 30000 });
  await page.waitForTimeout(2000);

  const sellerText = await page.textContent('body');
  if (sellerText.length > 50) {
    console.log(`  ✓ Seller dashboard loaded (${sellerText.length} chars)`);
    console.log(`  Preview: ${sellerText.substring(0, 200)}`);
    results.push('PASS: Seller dashboard loads');
  } else {
    console.log('  ✗ Seller dashboard empty');
    results.push('FAIL: Seller dashboard empty');
  }

  // ============ TEST 8: Check Bounties Page ============
  console.log('\n[Test 8] Check bounties...');
  await page.goto(`${BASE}/bounties`, { waitUntil: 'networkidle', timeout: 30000 });
  await page.waitForTimeout(2000);

  const bountyText = await page.textContent('body');
  if (bountyText.length > 50) {
    console.log(`  ✓ Bounties page loaded (${bountyText.length} chars)`);
    console.log(`  Preview: ${bountyText.substring(0, 200)}`);
    results.push('PASS: Bounties page loads');
  } else {
    console.log('  ✗ Bounties page empty');
    results.push('FAIL: Bounties page empty');
  }

  // ============ TEST 9: Check Sandbox Page ============
  console.log('\n[Test 9] Check sandbox...');
  await page.goto(`${BASE}/sandbox`, { waitUntil: 'networkidle', timeout: 30000 });
  await page.waitForTimeout(2000);

  const sandboxText = await page.textContent('body');
  if (sandboxText.length > 100) {
    console.log(`  ✓ Sandbox page loaded (${sandboxText.length} chars)`);
    console.log(`  Preview: ${sandboxText.substring(0, 200)}`);
    results.push('PASS: Sandbox page loads');
  } else {
    console.log('  ✗ Sandbox page empty');
    results.push('FAIL: Sandbox page empty');
  }

  // ============ TEST 10: Check Admin Page ============
  console.log('\n[Test 10] Check admin page...');
  await page.goto(`${BASE}/admin`, { waitUntil: 'networkidle', timeout: 30000 });
  await page.waitForTimeout(2000);

  const adminText = await page.textContent('body');
  if (adminText.length > 50) {
    console.log(`  ✓ Admin page loaded (${adminText.length} chars)`);
    console.log(`  Preview: ${adminText.substring(0, 200)}`);
    results.push('PASS: Admin page loads');
  } else {
    console.log('  ✗ Admin page empty');
    results.push('FAIL: Admin page empty');
  }

  // ============ Summary ============
  console.log('\n=== TEST RESULTS ===');
  results.forEach(r => console.log(r));

  if (errors.length > 0) {
    console.log('\n=== ERRORS ===');
    errors.forEach(e => console.log(e));
  }

  console.log(`\nTotal: ${results.length} tests, ${errors.length} errors`);

  await browser.close();
}

main().catch(e => {
  console.error('FATAL:', e.message);
  process.exit(1);
});
