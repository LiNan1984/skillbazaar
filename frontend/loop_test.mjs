import { chromium } from 'playwright';

const BASE = 'http://localhost:7788';
const API = 'http://localhost:8000';
const results = [];
const errors = [];

function assert(cond, label) {
  if (!cond) throw new Error(`FAIL: ${label}`);
  results.push(`PASS: ${label}`);
}

async function main() {
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({ viewport: { width: 1280, height: 900 } });
  const page = await context.newPage();

  // Capture console errors and response errors
  page.on('console', msg => {
    if (msg.type() === 'error') errors.push(`CONSOLE ERROR: ${msg.text()}`);
  });
  page.on('pageerror', err => errors.push(`PAGE ERROR: ${err.message}`));

  const responseErrors = [];
  page.on('response', async (resp) => {
    if (resp.status() >= 400) {
      const url = resp.url();
      try {
        const text = await resp.text();
        responseErrors.push(`${resp.status()}: ${url} -> ${text.substring(0, 200)}`);
      } catch(e) {
        responseErrors.push(`${resp.status()}: ${url}`);
      }
      console.error(`  RESPONSE ${resp.status()}: ${url}`);
    }
  });

  let apiToken = null;
  let testUserId = null;
  let productId = null;
  let bountyId = null;

  // ============ 1. Homepage ============
  console.log('[1] Loading homepage...');
  await page.goto(BASE, { waitUntil: 'networkidle', timeout: 30000 });
  await page.waitForTimeout(3000);
  const title = await page.title();
  assert(title.length > 0, 'Homepage has title');
  const bodyText = await page.textContent('body');
  assert(bodyText && bodyText.length > 100, 'Homepage has content');
  console.log(`[1] Homepage OK - title: "${title}", content: ${bodyText.length} chars`);

  // ============ 2. Register + Login via API ============
  console.log('[2] Registering user...');
  const rand = Math.random().toString(36).slice(2, 10);
  const username = `t${rand}`;

  // Register
  const regResp = await page.evaluate(async (args) => {
    try {
      const r = await fetch(`${args.api}/api/v2/auth/register`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(args.data)
      });
      const text = await r.text();
      let parsed;
      try { parsed = JSON.parse(text); } catch { parsed = text; }
      return { status: r.status, data: parsed };
    } catch (e) { return { status: 0, error: e.message }; }
  }, { api: API, data: { username, password: 'Test1234!', nickname: `TestUser${rand}` } });

  console.log(`[2] Register: ${regResp.status}`, JSON.stringify(regResp.data).slice(0, 200));
  if (regResp.status === 200 && regResp.data.user_id) {
    testUserId = regResp.data.user_id;
    // Login to get token
    console.log('[2b] Logging in to get token...');
    const loginResp = await page.evaluate(async (args) => {
      try {
        const r = await fetch(`${args.api}/api/v2/auth/login`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(args.data)
        });
        const text = await r.text();
        let parsed;
        try { parsed = JSON.parse(text); } catch { parsed = text; }
        return { status: r.status, data: parsed };
      } catch (e) { return { status: 0, error: e.message }; }
    }, { api: API, data: { username, password: 'Test1234!' } });

    console.log(`[2b] Login: ${loginResp.status}`, JSON.stringify(loginResp.data).slice(0, 200));
    if (loginResp.status === 200 && loginResp.data.token) {
      apiToken = loginResp.data.token;
      assert(!!apiToken, 'Login returns token');
    }
  } else if (regResp.status === 400 && regResp.data.detail && regResp.data.detail.includes('已存在')) {
    // Try login directly
    const loginResp = await page.evaluate(async (args) => {
      try {
        const r = await fetch(`${args.api}/api/v2/auth/login`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(args.data)
        });
        const text = await r.text();
        let parsed;
        try { parsed = JSON.parse(text); } catch { parsed = text; }
        return { status: r.status, data: parsed };
      } catch (e) { return { status: 0, error: e.message }; }
    }, { api: API, data: { username, password: 'Test1234!' } });
    console.log(`[2c] Login (existing): ${loginResp.status}`);
    if (loginResp.status === 200 && loginResp.data.token) {
      apiToken = loginResp.data.token;
      testUserId = loginResp.data.user_id;
      assert(!!apiToken, 'Login returns token for existing user');
    }
  }

  // ============ 3. Set auth in localStorage and reload ============
  if (apiToken && testUserId) {
    console.log(`[3] Setting auth for user ${testUserId}...`);
    await page.evaluate((t) => localStorage.setItem('skillbazaar_token', t), apiToken);
    await page.evaluate((u) => localStorage.setItem('skillbazaar_user_id', String(u)), testUserId);
    await page.evaluate((u) => localStorage.setItem('skillbazaar_username', String(u)), username);
    await page.goto(BASE, { waitUntil: 'networkidle', timeout: 30000 });
    await page.waitForTimeout(3000);

    const loggedIn = await page.textContent('body');
    const hasUser = loggedIn.includes('我的库') || loggedIn.includes('Library') ||
      loggedIn.includes('退出') || loggedIn.includes('nickname') || loggedIn.includes(username);
    assert(hasUser, 'Login state visible on homepage');
    console.log(`[3] Login UI OK`);
  }

  // ============ 4. Products API ============
  console.log('[4] Fetching products...');
  const productsResp = await page.evaluate(async (api) => {
    const r = await fetch(`${api}/api/products?limit=5`);
    return { status: r.status, data: await r.json().catch(() => ({})) };
  }, API);
  if (productsResp.status === 200) {
    const items = productsResp.data?.items || productsResp.data?.products || productsResp.data || [];
    assert(Array.isArray(items) && items.length > 0, 'Got products from API');
    productId = items[0].id;
    console.log(`[4] Got ${items.length} products, first id: ${productId}`);
  }

  // ============ 5. Product detail page ============
  if (productId) {
    console.log(`[5] Product detail page for ${productId}...`);
    await page.goto(`${BASE}/product/${productId}`, { waitUntil: 'networkidle', timeout: 30000 });
    await page.waitForTimeout(4000);
    await page.screenshot({ path: '/tmp/skbz_detail.png', fullPage: false });

    // Check for loading state or errors
    const loadingEl = await page.$('.detail-skeleton, .shimmer, .loading');
    if (loadingEl) {
      console.log('[5] WARNING: Still showing loading skeleton');
    }

    const detailText = await page.textContent('body');
    assert(detailText && detailText.length > 200, `Product detail page loaded for ${productId} (got ${detailText?.length || 0} chars)`);
    console.log(`[5] Product detail OK - ${detailText.length} chars`);
  }

  // ============ 6. Bounties page ============
  console.log('[6] Bounties page...');
  await page.goto(`${BASE}/bounties`, { waitUntil: 'networkidle', timeout: 30000 });
  await page.waitForTimeout(3000);
  await page.screenshot({ path: '/tmp/skbz_bounties.png', fullPage: false });
  const bountyText = await page.textContent('body');
  assert(bountyText && bountyText.length > 50, 'Bounties page loads');
  console.log(`[6] Bounties OK - ${bountyText.length} chars`);

  const bountiesResp = await page.evaluate(async (api) => {
    const r = await fetch(`${api}/api/bounties`);
    return { status: r.status, data: await r.json().catch(() => ({})) };
  }, API);
  if (bountiesResp.status === 200) {
    const bItems = bountiesResp.data?.items || bountiesResp.data?.bounties || bountiesResp.data || [];
    if (Array.isArray(bItems) && bItems.length > 0) bountyId = bItems[0].id;
    console.log(`[6b] Got ${bItems.length} bounties`);
  }

  // ============ 7. Library page ============
  if (apiToken) {
    console.log('[7] Library page...');
    await page.goto(`${BASE}/library`, { waitUntil: 'networkidle', timeout: 30000 });
    await page.waitForTimeout(3000);
    await page.screenshot({ path: '/tmp/skbz_library.png', fullPage: false });
    const libText = await page.textContent('body');
    assert(libText && libText.length > 0, 'Library page loads');
    console.log(`[7] Library OK - ${libText.length} chars`);
  }

  // ============ 8. Activities ============
  if (apiToken) {
    console.log('[8] Activities page...');
    await page.goto(`${BASE}/activities`, { waitUntil: 'networkidle', timeout: 30000 });
    await page.waitForTimeout(3000);
    await page.screenshot({ path: '/tmp/skbz_activities.png', fullPage: false });
    const actText = await page.textContent('body');
    assert(actText && actText.length > 0, 'Activities page loads');
    console.log(`[8] Activities OK - ${actText.length} chars`);
  }

  // ============ 9. Publish page ============
  if (apiToken) {
    console.log('[9] Publish page...');
    await page.goto(`${BASE}/publish`, { waitUntil: 'networkidle', timeout: 30000 });
    await page.waitForTimeout(3000);
    await page.screenshot({ path: '/tmp/skbz_publish.png', fullPage: false });
    const pubText = await page.textContent('body');
    assert(pubText && pubText.length > 0, 'Publish page loads');
    console.log(`[9] Publish OK - ${pubText.length} chars`);
  }

  // ============ 10. Seller dashboard ============
  if (apiToken) {
    console.log('[10] Seller dashboard...');
    await page.goto(`${BASE}/seller`, { waitUntil: 'networkidle', timeout: 30000 });
    await page.waitForTimeout(3000);
    await page.screenshot({ path: '/tmp/skbz_seller.png', fullPage: false });
    const sellerText = await page.textContent('body');
    assert(sellerText && sellerText.length > 0, 'Seller dashboard loads');
    console.log(`[10] Seller OK - ${sellerText.length} chars`);
  }

  // ============ 11. Sandbox page ============
  console.log('[11] Sandbox page...');
  await page.goto(`${BASE}/sandbox`, { waitUntil: 'networkidle', timeout: 30000 });
  await page.waitForTimeout(3000);
  await page.screenshot({ path: '/tmp/skbz_sandbox.png', fullPage: false });
  const sandboxText = await page.textContent('body');
  assert(sandboxText && sandboxText.length > 0, 'Sandbox page loads');
  console.log(`[11] Sandbox OK - ${sandboxText.length} chars`);

  // ============ 12. Admin page ============
  console.log('[12] Admin page...');
  await page.goto(`${BASE}/admin`, { waitUntil: 'networkidle', timeout: 30000 });
  await page.waitForTimeout(3000);
  await page.screenshot({ path: '/tmp/skbz_admin.png', fullPage: false });
  const adminText = await page.textContent('body');
  assert(adminText && adminText.length > 0, 'Admin page loads');
  console.log(`[12] Admin OK - ${adminText.length} chars`);

  // ============ Console errors ============
  if (errors.length > 0) {
    console.log('\n=== CONSOLE ERRORS ===');
    errors.forEach(e => console.log(e));
  }

  // ============ Response errors ============
  if (responseErrors.length > 0) {
    console.log('\n=== RESPONSE ERRORS ===');
    responseErrors.forEach(e => console.log(e));
  }

  // ============ Summary ============
  console.log('\n=== TEST RESULTS ===');
  results.forEach(r => console.log(r));
  console.log(`Total: ${results.length} tests passed, ${errors.length} console errors`);

  await browser.close();
  return { results, errors };
}

main().catch(e => {
  console.error('FATAL:', e.message);
  process.exit(1);
});
