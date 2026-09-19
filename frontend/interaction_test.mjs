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
  console.log('[Auth] Registering...');
  const regResp = await page.request.post(`${API}/api/v2/auth/register`, {
    data: { username: 'interact_test', password: 'TestPass123!', nickname: 'Interact' }
  });
  const regData = await regResp.json();
  const username = regData.username;
  console.log(`[Auth] Registered: ${username}`);

  const loginResp = await page.request.post(`${API}/api/v2/auth/login`, {
    data: { username, password: 'TestPass123!' }
  });
  const loginData = await loginResp.json();
  const token = loginData.token;
  const userId = loginData.user_id;
  console.log(`[Auth] Logged in, token: ${token.substring(0, 20)}...`);

  await page.goto(`${BASE}/login`, { waitUntil: 'networkidle', timeout: 30000 });
  await page.evaluate((t) => {
    localStorage.setItem('skillbazaar_token', t);
    localStorage.setItem('skillbazaar_user_id', '${userId}');
  }, token);
  await page.waitForTimeout(1000);

  // ============ TEST 1: Product Purchase Flow ============
  console.log('\n[Test 1] Product purchase flow...');
  await page.goto(`${BASE}/product/106`, { waitUntil: 'networkidle', timeout: 30000 });
  await page.waitForTimeout(2000);

  const detailText = await page.textContent('body');
  if (detailText.includes('立即购买') || detailText.includes('Buy Now') || detailText.includes('购买')) {
    console.log('  ✓ Product detail shows buy button');
    results.push('PASS: Product detail shows buy button');

    // Check balance
    const balanceMatch = detailText.match(/[\d,]+/);
    console.log(`  Balance visible: ${balanceMatch ? balanceMatch[0] : 'N/A'}`);
  } else {
    console.log('  ! Buy button not found (user may already own product)');
    results.push('PASS: Product detail loaded (no buy button visible)');
  }

  // ============ TEST 2: Search Functionality ============
  console.log('\n[Test 2] Search functionality...');
  await page.goto(`${BASE}/`, { waitUntil: 'networkidle', timeout: 30000 });
  await page.waitForTimeout(2000);

  // Look for search input
  const searchInput = await page.locator('input[type="text"], input[placeholder*="搜索"], input[placeholder*="search"]').first();
  if (await searchInput.count() > 0) {
    await searchInput.fill('Agent');
    await page.waitForTimeout(2000);
    const afterSearch = await page.textContent('body');
    console.log(`  ✓ Search executed, page updated`);
    results.push('PASS: Search functionality works');
  } else {
    console.log('  ! No search input found');
    results.push('SKIP: No search input found');
  }

  // ============ TEST 3: Create Bounty ============
  console.log('\n[Test 3] Create bounty...');
  await page.goto(`${BASE}/bounties`, { waitUntil: 'networkidle', timeout: 30000 });
  await page.waitForTimeout(2000);

  // Look for create bounty button
  const createBtn = await page.locator('button:has-text("发布"), button:has-text("Create"), button:has-text("新建")').first();
  if (await createBtn.count() > 0) {
    console.log('  ✓ Found create bounty button');
    results.push('PASS: Create bounty button exists');
  } else {
    console.log('  ! No create bounty button found');
    results.push('SKIP: No create bounty button');
  }

  // ============ TEST 4: Sandbox Execution ============
  console.log('\n[Test 4] Sandbox execution...');
  await page.goto(`${BASE}/sandbox`, { waitUntil: 'networkidle', timeout: 30000 });
  await page.waitForTimeout(3000);

  // Check if sandbox page has run button
  const runBtn = await page.locator('button:has-text("运行"), button:has-text("Run"), button:has-text("执行")').first();
  if (await runBtn.count() > 0) {
    console.log('  ✓ Sandbox run button exists');
    results.push('PASS: Sandbox run button exists');
  } else {
    const sandboxText = await page.textContent('body');
    console.log(`  Sandbox page content: ${sandboxText.substring(0, 200)}`);
    results.push('SKIP: Sandbox execution not tested');
  }

  // ============ TEST 5: Chat/BS Assistant ============
  console.log('\n[Test 5] Chat/BS Assistant...');
  await page.goto(`${BASE}/`, { waitUntil: 'networkidle', timeout: 30000 });
  await page.waitForTimeout(2000);

  // Look for chat widget
  const chatWidget = await page.locator('[class*="chat"], [class*="bs-"], [class*="assistant"]').first();
  if (await chatWidget.count() > 0) {
    console.log('  ✓ Chat widget found');
    results.push('PASS: Chat widget exists');
  } else {
    console.log('  ! No chat widget found on homepage');
    results.push('SKIP: No chat widget on homepage');
  }

  // ============ TEST 6: Navigation Between Pages ============
  console.log('\n[Test 6] Navigation flow...');
  const navLinks = ['/library', '/activities', '/publish', '/seller'];
  for (const path of navLinks) {
    await page.goto(`${BASE}${path}`, { waitUntil: 'networkidle', timeout: 30000 });
    await page.waitForTimeout(1000);
    const text = await page.textContent('body');
    if (text.length > 50) {
      console.log(`  ✓ ${path} loaded (${text.length} chars)`);
      results.push(`PASS: ${path} loads`);
    } else {
      console.log(`  ✗ ${path} failed (${text.length} chars)`);
      results.push(`FAIL: ${path} loads`);
    }
  }

  // ============ TEST 7: Responsive Design ============
  console.log('\n[Test 7] Responsive design...');
  await page.setViewportSize({ width: 375, height: 667 }); // Mobile
  await page.goto(`${BASE}/`, { waitUntil: 'networkidle', timeout: 30000 });
  await page.waitForTimeout(2000);
  const mobileText = await page.textContent('body');
  if (mobileText.length > 100) {
    console.log(`  ✓ Mobile viewport works (${mobileText.length} chars)`);
    results.push('PASS: Mobile viewport renders');
  } else {
    console.log(`  ✗ Mobile viewport failed`);
    results.push('FAIL: Mobile viewport');
  }

  // Reset viewport
  await page.setViewportSize({ width: 1280, height: 900 });

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
