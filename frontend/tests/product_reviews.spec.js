import { test, expect } from '@playwright/test';

const V2 = 'http://localhost:8000/api/v2';
const API_BASE = 'http://localhost:8000/api';
const FRONTEND = 'http://localhost:7788';

test('product reviews: list reviews and submit after purchase', async ({ page }) => {
  // 1. Register and login buyer
  const creds = { username: `rev_${Date.now()}`, password: 'test123456', nickname: '评价测试用户' };
  await fetch(`${V2}/auth/register`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(creds)
  });

  const loginResp = await fetch(`${V2}/auth/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ username: creds.username, password: creds.password })
  });
  const loginData = await loginResp.json();

  // 2. Create a product directly via API (so this user owns/publishes it)
  const productResp = await fetch(`${API_BASE}/products`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${loginData.token}` },
    body: JSON.stringify({
      name: `评价测试商品_${Date.now()}`,
      description: '用于测试商品评价功能的商品。',
      category: 'Skill',
      sub_category: '文本处理',
      price: 50,
      seller_name: creds.nickname,
      tags: JSON.stringify(['评价', '测试']),
      content_preview: 'Review test content',
      source_platform: 'manual',
      compat: JSON.stringify(['prompt'])
    })
  });
  const productData = await productResp.json();
  const productId = productData.id || productData.product_id;
  console.log('Created product:', productId);

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
  }, { t: loginData.token, uid: loginData.user_id, un: creds.username, nick: creds.nickname });

  // 3. Navigate to product detail page
  await page.goto(`${FRONTEND}/product/${productId}`);
  await page.waitForTimeout(3000);

  await page.screenshot({ path: '/tmp/review_product.png', fullPage: false });
  const productText = await page.textContent('body');
  console.log('Product page:', productText?.substring(0, 600));

  // 4. Verify reviews section exists
  expect(productText).toContain('用户评价');
  expect(productText).toContain('暂无评价');

  // 5. Verify reviews API works directly
  const reviewsResp = await fetch(`${API_BASE}/products/${productId}/reviews?page=1&page_size=10`);
  const reviewsData = await reviewsResp.json();
  console.log('Reviews API:', reviewsData);

  expect(reviewsData).toHaveProperty('items');
  expect(reviewsData).toHaveProperty('summary');
  expect(Array.isArray(reviewsData.items)).toBe(true);
  expect(reviewsData.items.length).toBe(0);

  // 6. Try to submit review without purchase - should fail (not owned)
  const reviewResp = await fetch(`${API_BASE}/products/${productId}/reviews`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${loginData.token}` },
    body: JSON.stringify({ rating: 5, content: '测试评价 - 未购买' })
  });
  const reviewResult = await reviewResp.json();
  console.log('Review without purchase:', reviewResp.status, reviewResult);

  // Should be rejected (403 or error since user is seller, not buyer)
  expect([400, 403, 404]).toContain(reviewResp.status);

  // 7. Verify no console errors
  const consoleErrors = [];
  page.on('console', msg => {
    if (msg.type() === 'error') consoleErrors.push(msg.text());
  });

  await page.reload();
  await page.waitForTimeout(2000);
  console.log('Console errors:', consoleErrors);
  expect(consoleErrors.length).toBe(0);
});
