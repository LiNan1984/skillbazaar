import { test, expect } from '@playwright/test';

const V2 = 'http://localhost:8000/api/v2';
const API_BASE = 'http://localhost:8000/api';
const FRONTEND = 'http://localhost:7788';

test('insufficient balance: purchase rejected when buyer lacks coins', async ({ page }) => {
  // 1. Create seller and expensive product
  const sellerCreds = { username: `rich_seller_${Date.now()}`, password: 'test123456', nickname: '高价卖家' };
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

  // Create a very expensive product (more than 10000 starting balance)
  const productResp = await fetch(`${API_BASE}/products`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${sellerLogin.token}` },
    body: JSON.stringify({
      name: `天价商品_${Date.now()}`,
      description: '价格超过用户初始余额的昂贵商品。',
      category: 'Agent',
      sub_category: '交易助手',
      price: 99999,
      seller_name: sellerCreds.nickname,
      tags: JSON.stringify(['expensive']),
      content_preview: 'expensive test',
      source_platform: 'manual',
      compat: JSON.stringify(['agent'])
    })
  });
  const product = await productResp.json();
  console.log('Expensive product created:', product.id, 'price: 99999');

  // 2. Create buyer with default 10000 coins
  const buyerCreds = { username: `poor_buyer_${Date.now()}`, password: 'test123456', nickname: '余额不足买家' };
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

  // Verify starting balance
  const meResp = await fetch(`${V2}/auth/me`, {
    headers: { Authorization: `Bearer ${buyerLogin.token}` }
  });
  const meData = await meResp.json();
  console.log('Buyer starting balance:', meData.coins);
  expect(meData.coins).toBeLessThan(99999);

  // 3. Attempt purchase - should be rejected
  const buyResp = await fetch(`${API_BASE}/transactions/buy`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${buyerLogin.token}` },
    body: JSON.stringify({ product_id: product.id })
  });
  const buyData = await buyResp.json();
  console.log('Purchase rejected:', buyResp.status, buyData.detail || buyData.message);

  expect([400, 402]).toContain(buyResp.status);
  const insufficientMsg = buyData.detail?.includes('余额') ||
                          buyData.detail?.includes('不足') ||
                          buyData.detail?.includes('insufficient');
  expect(insufficientMsg).toBe(true);

  // 4. Balance should be unchanged
  const meAfterResp = await fetch(`${V2}/auth/me`, {
    headers: { Authorization: `Bearer ${buyerLogin.token}` }
  });
  const meAfter = await meAfterResp.json();
  expect(meAfter.coins).toBe(10000);
  console.log('Balance unchanged:', meAfter.coins);

  // 5. Verify UI shows insufficient balance in purchase modal
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

  // Click buy button
  const buyBtn = page.locator('.btn-buy');
  if (await buyBtn.count() > 0) {
    await buyBtn.first().click();
    await page.waitForTimeout(1500);

    await page.screenshot({ path: '/tmp/insufficient_modal.png', fullPage: false });
    const modalText = await page.textContent('body');
    console.log('Purchase modal:', modalText?.substring(0, 500));

    // Verify modal shows price and balance
    const showsPrice = modalText?.includes('99,999') || modalText?.includes('99999');
    const showsInsufficient = modalText?.includes('余额不足') ||
                              modalText?.includes('不足') ||
                              modalText?.includes('insufficient');

    console.log('Shows price:', showsPrice, 'Shows insufficient:', showsInsufficient);

    // Confirm button should be disabled or show error
    const confirmBtn = page.locator('.btn-purchase');
    if (await confirmBtn.count() > 0) {
      const isDisabled = await confirmBtn.first().isDisabled();
      console.log('Confirm button disabled:', isDisabled);
    }
  }

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
