import { test, expect } from '@playwright/test';

const V2 = 'http://localhost:8000/api/v2';
const API_BASE = 'http://localhost:8000/api';
const FRONTEND = 'http://localhost:7788';

test('review after purchase: full buy then review flow', async ({ page }) => {
  // 1. Create seller user and product
  const sellerCreds = { username: `rseller_${Date.now()}`, password: 'test123456', nickname: '评价商品卖家' };
  await fetch(`${V2}/auth/register`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(sellerCreds)
  });

  const sellerLogin = await fetch(`${V2}/auth/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ username: sellerCreds.username, password: sellerCreds.password })
  }).then(r => r.json());

  const productResp = await fetch(`${API_BASE}/products`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${sellerLogin.token}` },
    body: JSON.stringify({
      name: `购买后评价商品_${Date.now()}`,
      description: '一个用于测试购买后评价流程的便宜商品。',
      category: 'Skill',
      sub_category: '文本处理',
      price: 10,
      seller_name: sellerCreds.nickname,
      tags: JSON.stringify(['review', 'test']),
      content_preview: 'Review flow test',
      source_platform: 'manual',
      compat: JSON.stringify(['prompt'])
    })
  });
  const productData = await productResp.json();
  const productId = productData.id;
  console.log('Seller created product:', productId);

  // 2. Create buyer user
  const buyerCreds = { username: `rbuyer_${Date.now()}`, password: 'test123456', nickname: '真实买家' };
  await fetch(`${V2}/auth/register`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(buyerCreds)
  });

  const buyerLogin = await fetch(`${V2}/auth/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ username: buyerCreds.username, password: buyerCreds.password })
  }).then(r => r.json());

  // 3. Buyer purchases via API
  const purchaseResp = await fetch(`${API_BASE}/transactions/buy`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${buyerLogin.token}` },
    body: JSON.stringify({ product_id: productId })
  });
  const purchaseData = await purchaseResp.json();
  console.log('Purchase status:', purchaseResp.status, purchaseData);
  expect(purchaseResp.status === 200 || purchaseResp.status === 201).toBe(true);

  // 4. Now buyer can review
  const reviewResp = await fetch(`${API_BASE}/products/${productId}/reviews`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${buyerLogin.token}` },
    body: JSON.stringify({ rating: 5, content: '非常好用的技能，测试评价！' })
  });
  const reviewData = await reviewResp.json();
  console.log('Review status:', reviewResp.status, reviewData);
  expect(reviewResp.status).toBe(200);
  expect(reviewData).toHaveProperty('review');
  expect(reviewData.review.rating).toBe(5);

  // 5. Verify review appears in list
  const listResp = await fetch(`${API_BASE}/products/${productId}/reviews?page=1&page_size=10`);
  const listData = await listResp.json();
  console.log('Reviews after submission:', listData.items?.length, 'summary:', listData.summary);

  expect(listData.items.length).toBe(1);
  expect(listData.items[0].rating).toBe(5);
  expect(listData.items[0].content).toContain('测试评价');
  expect(listData.summary.total).toBe(1);

  // 6. Verify duplicate review is rejected
  const dupResp = await fetch(`${API_BASE}/products/${productId}/reviews`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${buyerLogin.token}` },
    body: JSON.stringify({ rating: 3, content: '重复评价' })
  });
  console.log('Duplicate review status:', dupResp.status);
  expect([400, 403, 409]).toContain(dupResp.status);

  // 7. Verify UI shows review on product page
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
  }, { t: buyerLogin.token, uid: buyerLogin.user_id, un: buyerCreds.username, nick: buyerCreds.nickname });

  await page.goto(`${FRONTEND}/product/${productId}`);
  await page.waitForTimeout(3000);

  await page.screenshot({ path: '/tmp/review_after_purchase.png', fullPage: false });
  const pageText = await page.textContent('body');
  console.log('Product page with review:', pageText?.includes('非常好用'), pageText?.includes('真实买家'));

  expect(pageText).toContain('用户评价');
  expect(pageText).toContain('非常好用的技能');

  // 8. Verify no console errors
  const consoleErrors = [];
  page.on('console', msg => {
    if (msg.type() === 'error') consoleErrors.push(msg.text());
  });

  await page.reload();
  await page.waitForTimeout(2000);
  console.log('Console errors:', consoleErrors);
  expect(consoleErrors.length).toBe(0);
});
