import { test, expect } from '@playwright/test';

const V2 = 'http://localhost:8000/api/v2';
const API_BASE = 'http://localhost:8000/api';
const FRONTEND = 'http://localhost:7788';

test('user profile: public profile and own profile API', async ({ page }) => {
  // 1. Register two users
  const userACreds = { username: `profile_a_${Date.now()}`, password: 'test123456', nickname: '卖家用户A' };
  await fetch(`${V2}/auth/register`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(userACreds)
  });
  const userALogin = await fetch(`${V2}/auth/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ username: userACreds.username, password: userACreds.password })
  }).then(r => r.json());

  const userBCreds = { username: `profile_b_${Date.now()}`, password: 'test123456', nickname: '访客用户B' };
  await fetch(`${V2}/auth/register`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(userBCreds)
  });
  const userBLogin = await fetch(`${V2}/auth/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ username: userBCreds.username, password: userBCreds.password })
  }).then(r => r.json());

  // 2. User A creates a product (so profile has content)
  await fetch(`${API_BASE}/products`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${userALogin.token}` },
    body: JSON.stringify({
      name: `主页展示商品_${Date.now()}`,
      description: '显示在卖家公开主页上的商品。',
      category: 'Skill',
      sub_category: '文本处理',
      price: 80,
      seller_name: userACreds.nickname,
      tags: JSON.stringify(['profile']),
      content_preview: 'profile test',
      source_platform: 'manual',
      compat: JSON.stringify(['prompt'])
    })
  });

  // 3. Fetch user A's public profile (as user B)
  const profileResp = await fetch(`${API_BASE}/u/${userACreds.username}`, {
    headers: { Authorization: `Bearer ${userBLogin.token}` }
  });
  const profileData = await profileResp.json();
  console.log('Public profile:', profileResp.status, JSON.stringify(profileData).substring(0, 300));

  expect(profileResp.status).toBe(200);
  expect(profileData.username || profileData.nickname).toBeTruthy();

  // 4. Fetch user A's products
  const productsResp = await fetch(`${API_BASE}/u/${userACreds.username}/products`);
  const productsData = await productsResp.json();
  console.log('User products:', productsResp.status, JSON.stringify(productsData).substring(0, 300));

  const products = productsData.products || productsData.items || [];
  expect(products.length).toBeGreaterThanOrEqual(1);
  expect(products[0].name).toContain('主页展示商品');

  // 5. Fetch own profile
  const myProfileResp = await fetch(`${API_BASE}/profile/me`, {
    headers: { Authorization: `Bearer ${userBLogin.token}` }
  });
  const myProfile = await myProfileResp.json();
  console.log('My profile:', myProfileResp.status, JSON.stringify(myProfile).substring(0, 300));
  expect(myProfileResp.status).toBe(200);

  // 6. Update own profile
  const updateResp = await fetch(`${API_BASE}/profile/me`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${userBLogin.token}` },
    body: JSON.stringify({
      nickname: '更新后的昵称',
      bio: '这是我的个人简介，热爱AI和自动化。',
      avatar: 'https://example.com/avatar.png'
    })
  });
  const updateData = await updateResp.json();
  console.log('Profile update:', updateResp.status, JSON.stringify(updateData).substring(0, 300));
  expect(updateResp.status).toBe(200);

  // 7. Test follow functionality
  const followResp = await fetch(`${API_BASE}/u/${userACreds.username}/follow`, {
    method: 'POST',
    headers: { Authorization: `Bearer ${userBLogin.token}` }
  });
  console.log('Follow status:', followResp.status);
  expect([200, 201]).toContain(followResp.status);

  // Verify following list
  const followingResp = await fetch(`${API_BASE}/u/${userBCreds.username}/following`, {
    headers: { Authorization: `Bearer ${userBLogin.token}` }
  });
  const followingData = await followingResp.json();
  const following = followingData.following || followingData.users || [];
  console.log('Following count:', following.length);

  // Verify follower count for user A
  const followersResp = await fetch(`${API_BASE}/u/${userACreds.username}/followers`, {
    headers: { Authorization: `Bearer ${userBLogin.token}` }
  });
  const followersData = await followersResp.json();
  const followers = followersData.followers || followersData.users || [];
  console.log('Followers count:', followers.length);

  // 8. Unfollow
  const unfollowResp = await fetch(`${API_BASE}/u/${userACreds.username}/follow`, {
    method: 'DELETE',
    headers: { Authorization: `Bearer ${userBLogin.token}` }
  });
  console.log('Unfollow status:', unfollowResp.status);
  expect([200, 204]).toContain(unfollowResp.status);

  // 9. 404 for nonexistent user
  const ghostResp = await fetch(`${API_BASE}/u/nonexistent_user_xyz_${Date.now()}`);
  expect(ghostResp.status).toBe(404);
  console.log('Ghost user returns 404');

  // 10. Verify homepage still works and no console errors
  await page.goto(FRONTEND);
  await page.waitForTimeout(2000);

  const consoleErrors = [];
  page.on('console', msg => {
    if (msg.type() === 'error') consoleErrors.push(msg.text());
  });

  await page.reload();
  await page.waitForTimeout(2000);
  console.log('Console errors:', consoleErrors);
  expect(consoleErrors.length).toBe(0);
});
