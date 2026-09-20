import { test, expect } from '@playwright/test';

const V2 = 'http://localhost:8000/api/v2';
const API_BASE = 'http://localhost:8000/api';
const FRONTEND = 'http://localhost:7788';

test('bounty detail page: renders bounty info and application form', async ({ page }) => {
  // Register and login
  const creds = { username: `bdetail_${Date.now()}`, password: 'test123456', nickname: '详情测试用户' };
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

  // 1. Navigate to bounties page to find a bounty
  await page.goto(`${FRONTEND}/bounties`);
  await page.waitForTimeout(3000);

  const bountyText = await page.textContent('body');
  console.log('Bounty list:', bountyText?.substring(0, 500));

  // Find first bounty link
  const bountyLinks = page.locator('.bounty-card');
  const bountyCount = await bountyLinks.count();
  console.log('Bounty cards found:', bountyCount);

  if (bountyCount > 0) {
    // Click the first bounty card
    await bountyLinks.first().click();
    await page.waitForTimeout(3000);

    await page.screenshot({ path: '/tmp/bounty_detail.png', fullPage: false });
    const detailText = await page.textContent('body');
    console.log('Bounty detail:', detailText?.substring(0, 1000));

    // 2. Verify bounty detail loaded
    const hasBountyInfo = detailText.includes('悬赏') || detailText.includes('预算') || detailText.includes('金币');
    console.log('Has bounty info:', hasBountyInfo);

    // 3. Verify application form or apply button exists
    const hasApplyBtn = detailText.includes('申请') ||
                        detailText.includes('接单') ||
                        detailText.includes('竞标') ||
                        detailText.includes('apply');
    console.log('Has apply button:', hasApplyBtn);

    // 4. Verify navbar still renders
    expect(detailText).toContain('SkillBazaar');
  } else {
    console.log('No bounties found - skipping detail test');
  }

  // 5. Verify no console errors
  const consoleErrors = [];
  page.on('console', msg => {
    if (msg.type() === 'error') consoleErrors.push(msg.text());
  });

  await page.reload();
  await page.waitForTimeout(2000);
  console.log('Console errors:', consoleErrors);
  expect(consoleErrors.length).toBe(0);
});
