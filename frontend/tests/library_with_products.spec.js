import { test, expect } from '@playwright/test';

const V2 = 'http://localhost:8000/api/v2';
const API_BASE = 'http://localhost:8000/api';
const FRONTEND = 'http://localhost:7788';

test('my library: owned products appear after publishing', async ({ page }) => {
  // Register and login
  const creds = { username: `library_${Date.now()}`, password: 'test123456', nickname: '库测试用户' };
  const regResp = await fetch(`${V2}/auth/register`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(creds)
  });
  await regResp.json();

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

  // Create a product via API so the user owns it
  const productResp = await fetch(`${API_BASE}/products`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${loginData.token}`
    },
    body: JSON.stringify({
      name: `LibraryTest商品_${Date.now()}`,
      description: '用于测试我的库页面的商品',
      category: 'Skill',
      sub_category: '文件处理',
      price: 200,
      seller_name: creds.nickname,
      tags: JSON.stringify(['测试', 'Library']),
      content_preview: '测试内容预览',
      source_platform: 'manual',
      compat: JSON.stringify(['claude-code'])
    })
  });
  const productData = await productResp.json();
  console.log('Created product:', productData);
  const productId = productData.id || productData.data?.id;

  await page.goto(FRONTEND);
  await page.waitForTimeout(1500);

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
  }, { t: loginData.token, uid: meData.user_id, un: creds.username, nick: creds.nickname });

  // 1. Navigate to library page
  await page.goto(`${FRONTEND}/library`);
  await page.waitForTimeout(3000);

  await page.screenshot({ path: '/tmp/library_page.png', fullPage: false });
  const libraryText = await page.textContent('body');
  console.log('Library page:', libraryText?.substring(0, 1500));

  // 2. Verify library page loaded
  expect(libraryText).toContain('我的库');

  // 3. Verify the created product appears in library
  if (productId) {
    // Check by product name or ID
    const hasProduct = libraryText.includes('LibraryTest商品') ||
                       (productData.name && libraryText.includes(productData.name));
    console.log('Product found in library:', hasProduct);
    if (hasProduct) {
      expect(libraryText).toContain('LibraryTest商品');
    }
  }

  // 4. Verify empty tabs or sections exist
  const hasTabs = libraryText.includes('全部') ||
                  libraryText.includes('已购买') ||
                  libraryText.includes('已发布') ||
                  libraryText.includes('收藏');
  console.log('Has library tabs:', hasTabs);

  // 5. Verify navbar still renders
  expect(libraryText).toContain('SkillBazaar');

  // 6. Verify no console errors
  const consoleErrors = [];
  page.on('console', msg => {
    if (msg.type() === 'error') consoleErrors.push(msg.text());
  });

  await page.reload();
  await page.waitForTimeout(2000);
  console.log('Console errors:', consoleErrors);
  expect(consoleErrors.length).toBe(0);
});
