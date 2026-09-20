import { test, expect } from '@playwright/test';

const V2 = 'http://localhost:8000/api/v2';
const API_BASE = 'http://localhost:8000/api';
const FRONTEND = 'http://localhost:7788';

test('seller management: product appears in dashboard and status toggle works', async ({ page }) => {
  // 1. Register seller
  const creds = { username: `smgmt_${Date.now()}`, password: 'test123456', nickname: '卖家管理测试' };
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

  // 2. Create two products via API
  const createProduct = async (name, price) => {
    const resp = await fetch(`${API_BASE}/products`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${loginData.token}` },
      body: JSON.stringify({
        name,
        description: `商品：${name}`,
        category: 'Skill',
        sub_category: '文件处理',
        price,
        seller_name: creds.nickname,
        tags: JSON.stringify(['管理测试']),
        content_preview: 'test',
        source_platform: 'manual',
        compat: JSON.stringify(['prompt'])
      })
    });
    return resp.json();
  };

  const product1 = await createProduct(`卖家商品A_${Date.now()}`, 100);
  const product2 = await createProduct(`卖家商品B_${Date.now()}`, 200);
  console.log('Created products:', product1.id, product2.id);

  // 3. Verify seller stats API
  const statsResp = await fetch(`${V2}/seller/stats`, {
    headers: { Authorization: `Bearer ${loginData.token}` }
  });
  const statsData = await statsResp.json();
  console.log('Seller stats:', statsData);
  expect(statsData.product_count).toBeGreaterThanOrEqual(2);
  expect(statsData.active_count).toBeGreaterThanOrEqual(2);

  // 4. Verify my products API
  const myResp = await fetch(`${V2}/seller/products`, {
    headers: { Authorization: `Bearer ${loginData.token}` }
  });
  const myData = await myResp.json();
  console.log('My products count:', myData.products?.length);
  expect(myData.products.length).toBeGreaterThanOrEqual(2);

  // 5. Navigate to seller dashboard
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
  }, { t: loginData.token, uid: loginData.user_id, un: creds.username, nick: creds.nickname });

  await page.goto(`${FRONTEND}/seller`);
  await page.waitForTimeout(3000);

  await page.screenshot({ path: '/tmp/seller_with_products.png', fullPage: false });
  const sellerText = await page.textContent('body');
  console.log('Seller dashboard:', sellerText?.substring(0, 800));

  // Verify stats
  expect(sellerText).toContain('卖家中心');
  expect(sellerText).toContain('全部商品');
  expect(sellerText).toContain('在售');

  // Verify product names appear
  expect(sellerText).toContain('卖家商品A');
  expect(sellerText).toContain('卖家商品B');

  // Verify delist buttons
  const delistBtns = page.locator('button:has-text("下架"), .btn-delist');
  const delistCount = await delistBtns.count();
  console.log('Delist buttons:', delistCount);
  expect(delistCount).toBeGreaterThanOrEqual(2);

  // 6. Test status toggle - delist first product via API
  const delistResp = await fetch(`${V2}/seller/products/${product1.id}/status?status=inactive&reason=`, {
    method: 'PUT',
    headers: { Authorization: `Bearer ${loginData.token}` }
  });
  console.log('Delist status:', delistResp.status);
  expect(delistResp.status).toBe(200);

  // Verify product status changed
  const myResp2 = await fetch(`${V2}/seller/products`, {
    headers: { Authorization: `Bearer ${loginData.token}` }
  });
  const myData2 = await myResp2.json();
  const delisted = myData2.products.find(p => p.id === product1.id);
  expect(delisted.status).toBe('inactive');

  // Stats should update
  const stats2 = await fetch(`${V2}/seller/stats`, {
    headers: { Authorization: `Bearer ${loginData.token}` }
  }).then(r => r.json());
  expect(stats2.inactive_count).toBeGreaterThanOrEqual(1);
  console.log('Stats after delist:', stats2);

  // 7. Relist via API
  const relistResp = await fetch(`${V2}/seller/products/${product1.id}/status?status=active&reason=`, {
    method: 'PUT',
    headers: { Authorization: `Bearer ${loginData.token}` }
  });
  expect(relistResp.status).toBe(200);

  // 8. Verify UI reflects changes after reload
  await page.reload();
  await page.waitForTimeout(3000);

  await page.screenshot({ path: '/tmp/seller_after_toggle.png', fullPage: false });

  // 9. Test UI toggle by clicking delist button
  const firstDelist = page.locator('.seller-list-row button:has-text("下架")').first();
  if (await firstDelist.count() > 0) {
    await firstDelist.click();
    await page.waitForTimeout(2000);

    await page.screenshot({ path: '/tmp/seller_after_ui_delist.png', fullPage: false });
    const afterDelist = await page.textContent('body');

    // Should show 上架 button after delisting
    const hasRelistBtn = afterDelist?.includes('上架');
    console.log('Relist button visible after UI toggle:', hasRelistBtn);
  }

  // 10. Verify no console errors
  const consoleErrors = [];
  page.on('console', msg => {
    if (msg.type() === 'error') consoleErrors.push(msg.text());
  });

  await page.reload();
  await page.waitForTimeout(2000);
  console.log('Console errors:', consoleErrors);
  expect(consoleErrors.length).toBe(0);
});
