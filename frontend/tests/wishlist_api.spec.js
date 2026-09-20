import { test, expect } from '@playwright/test';

const V2 = 'http://localhost:8000/api/v2';
const API_BASE = 'http://localhost:8000/api';

test('wishlist API: add, list, remove products', async () => {
  // Register
  const creds = { username: `wish_${Date.now()}`, password: 'test123456', nickname: '收藏测试用户' };
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

  // Use existing product id 106 (mcporter)
  const productId = 106;

  // 1. Add to wishlist
  const addResp = await fetch(`${API_BASE}/v4/wishlist/${productId}`, {
    method: 'POST',
    headers: { Authorization: `Bearer ${login.token}` }
  });
  console.log('Add wishlist:', addResp.status);
  expect([200, 201]).toContain(addResp.status);

  // 2. List wishlist
  const listResp = await fetch(`${API_BASE}/v4/wishlist`, {
    headers: { Authorization: `Bearer ${login.token}` }
  });
  const listData = await listResp.json();
  console.log('Wishlist items:', listData.items?.length || listData.length);
  const items = listData.items || listData || [];
  expect(items.length).toBeGreaterThanOrEqual(1);

  // 3. Add duplicate - should be idempotent or rejected
  const dupResp = await fetch(`${API_BASE}/v4/wishlist/${productId}`, {
    method: 'POST',
    headers: { Authorization: `Bearer ${login.token}` }
  });
  console.log('Duplicate add:', dupResp.status);
  expect([200, 201, 400, 409]).toContain(dupResp.status);

  // 4. Remove from wishlist
  const delResp = await fetch(`${API_BASE}/v4/wishlist/${productId}`, {
    method: 'DELETE',
    headers: { Authorization: `Bearer ${login.token}` }
  });
  console.log('Remove wishlist:', delResp.status);
  expect([200, 204]).toContain(delResp.status);

  // 5. Verify empty
  const listAfter = await fetch(`${API_BASE}/v4/wishlist`, {
    headers: { Authorization: `Bearer ${login.token}` }
  }).then(r => r.json());
  const itemsAfter = listAfter.items || listAfter || [];
  expect(itemsAfter.length).toBe(0);
  console.log('Wishlist cleared');

  // 6. Remove non-existent - should not 500
  const ghostDel = await fetch(`${API_BASE}/v4/wishlist/99999999`, {
    method: 'DELETE',
    headers: { Authorization: `Bearer ${login.token}` }
  });
  console.log('Ghost remove:', ghostDel.status);
  expect([200, 204, 404]).toContain(ghostDel.status);

  // 7. Unauthenticated access rejected
  const unauthResp = await fetch(`${API_BASE}/v4/wishlist`);
  expect([401, 403]).toContain(unauthResp.status);
  console.log('Unauthenticated blocked');
});
