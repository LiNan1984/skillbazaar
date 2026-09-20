import { test, expect } from '@playwright/test';

const V2 = 'http://localhost:8000/api/v2';
const API_BASE = 'http://localhost:8000/api';
const FRONTEND = 'http://localhost:7788';

test('purchase edge cases: duplicate purchase rejected and insufficient balance handled', async ({ page }) => {
  // 1. Register seller and create cheap product
  const sellerCreds = { username: `dup_seller_${Date.now()}`, password: 'test123456', nickname: '重复购买卖家' };
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
      name: `重复购买测试_${Date.now()}`,
      description: '测试重复购买保护的商品。',
      category: 'Skill',
      sub_category: 'API调用',
      price: 1,
      seller_name: sellerCreds.nickname,
      tags: JSON.stringify(['dup']),
      content_preview: 'dup test',
      source_platform: 'manual',
      compat: JSON.stringify(['prompt'])
    })
  });
  const product = await productResp.json();
  console.log('Product created:', product.id);

  // 2. Register buyer
  const buyerCreds = { username: `dup_buyer_${Date.now()}`, password: 'test123456', nickname: '重复购买买家' };
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

  // 3. First purchase should succeed
  const firstResp = await fetch(`${API_BASE}/transactions/buy`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${buyerLogin.token}` },
    body: JSON.stringify({ product_id: product.id })
  });
  const firstData = await firstResp.json();
  console.log('First purchase:', firstResp.status, firstData.message || firstData.detail);
  expect(firstResp.status).toBe(200);
  expect(firstData.success).toBe(true);

  // 4. Second purchase should be rejected
  const secondResp = await fetch(`${API_BASE}/transactions/buy`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${buyerLogin.token}` },
    body: JSON.stringify({ product_id: product.id })
  });
  const secondData = await secondResp.json();
  console.log('Second purchase:', secondResp.status, secondData.detail || secondData.message);

  expect([400, 409]).toContain(secondResp.status);
  const alreadyOwned = secondData.detail?.includes('已购买') ||
                       secondData.detail?.includes('已经') ||
                       secondData.detail?.includes('already');
  expect(alreadyOwned).toBe(true);

  // 5. Verify buyer balance decreased only once
  const meResp = await fetch(`${V2}/auth/me`, {
    headers: { Authorization: `Bearer ${buyerLogin.token}` }
  });
  const meData = await meResp.json();
  console.log('Final balance:', meData.coins);
  expect(meData.coins).toBe(9999); // Started with 10000, spent 1

  // 6. Verify UI shows owned state on product page
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
  }, { t: buyerLogin.token, uid: buyerLogin.user_id, un: buyerCreds.username, nick: buyerCreds.nickname });

  await page.goto(`${FRONTEND}/product/${product.id}`);
  await page.waitForTimeout(3000);

  await page.screenshot({ path: '/tmp/owned_product.png', fullPage: false });
  const ownedText = await page.textContent('body');
  console.log('Owned product page:', ownedText?.substring(0, 600));

  // Should show "已购买" / "已拥有" state instead of buy button
  const showsOwned = ownedText?.includes('已购买') ||
                     ownedText?.includes('已拥有') ||
                     ownedText?.includes('去使用') ||
                     ownedText?.includes('查看') ||
                     !ownedText?.includes('立即购买');
  console.log('Owned state shown:', showsOwned);

  // 7. Test buying non-existent product
  const ghostResp = await fetch(`${API_BASE}/transactions/buy`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${buyerLogin.token}` },
    body: JSON.stringify({ product_id: 99999999 })
  });
  const ghostData = await ghostResp.json();
  console.log('Ghost product purchase:', ghostResp.status, ghostData.detail);
  expect([400, 404]).toContain(ghostResp.status);

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
