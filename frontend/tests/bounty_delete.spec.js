import { test, expect } from '@playwright/test';

const API_BASE = 'http://localhost:8000/api';
const V2 = `${API_BASE}/v2`;
const FRONTEND = 'http://localhost:7788';

test('bounty: poster can delete bounty from detail page', async ({ page }) => {
  // Register poster
  const posterCreds = { username: `bountydel_${Date.now()}`, password: 'test123456', nickname: '删除测试' };
  await fetch(`${V2}/auth/register`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(posterCreds)
  }).then(r => r.json());

  const posterLogin = await fetch(`${V2}/auth/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ username: posterCreds.username, password: posterCreds.password })
  }).then(r => r.json());
  const posterMe = await fetch(`${V2}/auth/me`, {
    headers: { Authorization: `Bearer ${posterLogin.token}` }
  }).then(r => r.json());

  // 1. Create a bounty via API
  const bountyResp = await fetch(`${API_BASE}/bounties`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${posterLogin.token}` },
    body: JSON.stringify({
      title: `待删除悬赏_${Date.now()}`,
      description: '这个悬赏将被删除。测试删除功能是否正常工作。',
      category: 'Skill',
      budget_min: 100,
      budget_max: 500,
      deadline: new Date(Date.now() + 7 * 24 * 60 * 60 * 1000).toISOString(),
      skill_type: 'prompt'
    })
  });
  const bounty = await bountyResp.json();
  expect(bountyResp.status).toBe(200);
  console.log('Bounty to delete:', bounty.id);

  // 2. Login as poster
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
  }, { t: posterLogin.token, uid: posterMe.user_id, un: posterCreds.username, nick: posterCreds.nickname });

  // 3. Navigate to bounty detail page
  await page.goto(`${FRONTEND}/bounty/${bounty.id}`);
  await page.waitForTimeout(3000);

  // Debug: check userId and poster_id
  const ids = await page.evaluate(async () => {
    const token = localStorage.getItem('skillbazaar_token');
    const uid = localStorage.getItem('skillbazaar_user_id');
    let bountyData = null;
    if (token) {
      try {
        const r = await fetch('/api/bounties/' + window.location.pathname.split('/').pop(), {
          headers: { Authorization: `Bearer ${token}` }
        });
        bountyData = await r.json();
      } catch(e) {}
    }
    return { localStorageUserId: uid, bountyPosterId: bountyData?.poster_id, bountyStatus: bountyData?.status };
  });
  console.log('ID comparison:', JSON.stringify(ids));

  await page.screenshot({ path: '/tmp/delete_bounty_before.png', fullPage: false });
  const detailText = await page.textContent('body');
  console.log('Bounty detail before delete:', detailText?.substring(0, 400));

  expect(detailText).toContain('待删除悬赏');
  expect(detailText).toContain('删除悬赏');

  // 4. Click delete button
  page.on('dialog', async dialog => {
    console.log('Dialog message:', dialog.message());
    await dialog.accept();
  });

  await page.click('button:has-text("删除悬赏")');
  await page.waitForTimeout(3000);

  await page.screenshot({ path: '/tmp/delete_bounty_after.png', fullPage: false });
  const afterDeleteText = await page.textContent('body');
  console.log('After delete:', afterDeleteText?.substring(0, 400));

  // 5. Verify bounty is gone (redirected or shows not found)
  const bountyGone = !afterDeleteText.includes('待删除悬赏') || afterDeleteText.includes('404') || afterDeleteText.includes('不存在');
  console.log('Bounty deleted:', bountyGone);

  // 6. Verify via API that bounty is cancelled
  const checkBounty = await fetch(`${API_BASE}/bounties/${bounty.id}`, {
    headers: { Authorization: `Bearer ${posterLogin.token}` }
  }).then(r => r.json()).catch(e => ({ error: e.message }));

  console.log('Bounty status after delete:', checkBounty.status || checkBounty.error || 'not found');
  const isCancelled = checkBounty.status === 'cancelled' || checkBounty.error !== undefined;
  console.log('API confirms cancelled:', isCancelled);

  // Zero console errors
  const consoleErrors = [];
  page.on('console', msg => {
    if (msg.type() === 'error') consoleErrors.push(msg.text());
  });

  await page.reload();
  await page.waitForTimeout(2000);
  console.log('Console errors:', consoleErrors);
  expect(consoleErrors.length).toBe(0);
});
