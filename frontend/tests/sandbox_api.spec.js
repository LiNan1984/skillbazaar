import { test, expect } from '@playwright/test';

const V2 = 'http://localhost:8000/api/v2';
const API_BASE = 'http://localhost:8000/api';
const FRONTEND = 'http://localhost:7788';

test('sandbox API: status, quota and developer API key management', async ({ page }) => {
  const creds = { username: `sandbox_api_${Date.now()}`, password: 'test123456', nickname: '沙盒API测试' };
  await fetch(`${V2}/auth/register`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(creds)
  });
  const login = await fetch(`${V2}/auth/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ username: creds.username, password: creds.password })
  }).then(r => r.json());

  const authHeaders = { Authorization: `Bearer ${login.token}` };

  // 1. Check sandbox status
  const statusResp = await fetch(`${API_BASE}/sandbox/status`, { headers: authHeaders });
  console.log('Sandbox status:', statusResp.status);
  expect(statusResp.status).toBe(200);
  const status = await statusResp.json();
  console.log('Status data:', JSON.stringify(status).substring(0, 200));

  // 2. Check API keys list (empty initially)
  const keysResp = await fetch(`${API_BASE}/sandbox/api-keys`, { headers: authHeaders });
  console.log('API keys status:', keysResp.status);
  expect(keysResp.status).toBe(200);
  const keysData = await keysResp.json();
  const keys = keysData.keys || keysData.items || [];
  console.log('Initial API keys:', keys.length);

  // 3. Create an API key
  const createKeyResp = await fetch(`${API_BASE}/sandbox/api-keys`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...authHeaders },
    body: JSON.stringify({ name: 'E2E测试密钥' })
  });
  console.log('Create key status:', createKeyResp.status);

  if (createKeyResp.status === 200 || createKeyResp.status === 201) {
    const newKey = await createKeyResp.json();
    console.log('Created key:', JSON.stringify(newKey).substring(0, 200));

    // Key value should only be shown once
    expect(newKey.key || newKey.api_key || newKey.token).toBeTruthy();

    // Verify key appears in list
    const keysAfter = await fetch(`${API_BASE}/sandbox/api-keys`, { headers: authHeaders }).then(r => r.json());
    const keysList = keysAfter.keys || keysAfter.items || [];
    expect(keysList.length).toBeGreaterThanOrEqual(1);
    console.log('Keys after create:', keysList.length);

    // Delete the key
    const keyId = newKey.id || keysList[0].id;
    if (keyId) {
      const delResp = await fetch(`${API_BASE}/sandbox/api-keys/${keyId}`, {
        method: 'DELETE',
        headers: authHeaders
      });
      console.log('Delete key:', delResp.status);
      expect([200, 204]).toContain(delResp.status);
    }
  } else {
    const errBody = await createKeyResp.text();
    console.log('Key creation response:', errBody.substring(0, 200));
  }

  // 4. Test unauthenticated access
  const unauthStatus = await fetch(`${API_BASE}/sandbox/status`);
  expect([401, 403]).toContain(unauthStatus.status);
  console.log('Unauthenticated blocked');

  // 5. Navigate to sandbox page and verify developer tab
  await page.goto(FRONTEND);
  await page.waitForTimeout(1000);

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
  }, { t: login.token, uid: login.user_id, un: creds.username, nick: creds.nickname });

  await page.goto(`${FRONTEND}/sandbox`);
  await page.waitForTimeout(2000);

  // Click developer tab
  const devTab = page.locator('button:has-text("开发者")');
  if (await devTab.count() > 0) {
    await devTab.first().click();
    await page.waitForTimeout(1500);

    await page.screenshot({ path: '/tmp/sandbox_developer.png', fullPage: false });
    const devText = await page.textContent('body');
    console.log('Developer tab:', devText?.substring(0, 400));

    // Should show API documentation or key management
    const hasDevContent = devText?.includes('API') ||
                          devText?.includes('密钥') ||
                          devText?.includes('key') ||
                          devText?.includes('开发者');
    expect(hasDevContent).toBe(true);
  }

  // 6. No console errors
  const consoleErrors = [];
  page.on('console', msg => {
    if (msg.type() === 'error') consoleErrors.push(msg.text());
  });

  await page.reload();
  await page.waitForTimeout(2000);
  console.log('Console errors:', consoleErrors);
  expect(consoleErrors.length).toBe(0);
});
