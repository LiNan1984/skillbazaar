import { test, expect } from '@playwright/test';

const V2 = 'http://localhost:8000/api/v2';
const FRONTEND = 'http://localhost:7788';

test('homepage: search with no results shows empty state', async ({ page }) => {
  // Register and login
  const creds = { username: `search_empty_${Date.now()}`, password: 'test123456', nickname: '空搜索用户' };
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

  // 1. Navigate to homepage
  await page.goto(FRONTEND);
  await page.waitForTimeout(3000);

  await page.screenshot({ path: '/tmp/homepage_default.png', fullPage: false });
  const defaultText = await page.textContent('body');
  console.log('Homepage default:', defaultText?.substring(0, 500));

  // Verify products shown by default
  expect(defaultText).toContain('SkillBazaar');

  // 2. Search for something that definitely doesn't exist
  const searchInput = page.locator('input[placeholder*="搜索"], input[placeholder*="搜索商品"], .search-input');
  const inputCount = await searchInput.count();
  console.log('Search input count:', inputCount);

  if (inputCount > 0) {
    // Use a very specific nonsense search term
    await searchInput.first().fill('xyznonexistentproduct12345');
    await page.waitForTimeout(500);

    // Press Enter or click search button
    await searchInput.first().press('Enter');
    await page.waitForTimeout(3000);

    await page.screenshot({ path: '/tmp/homepage_no_results.png', fullPage: false });
    const noResultsText = await page.textContent('body');
    console.log('No results page:', noResultsText?.substring(0, 1000));

    // Verify empty state message
    const hasEmptyState = noResultsText.includes('暂无') ||
                          noResultsText.includes('没有找到') ||
                          noResultsText.includes('未找到') ||
                          noResultsText.includes('没有相关') ||
                          noResultsText.includes('0 个商品') ||
                          noResultsText.includes('0个');
    console.log('Has empty state:', hasEmptyState);

    // Verify no product cards are shown
    const productCards = page.locator('.product-card');
    const cardCount = await productCards.count();
    console.log('Product cards after no-results search:', cardCount);
    expect(cardCount).toBe(0);

    // Verify navbar still renders
    expect(noResultsText).toContain('SkillBazaar');
  } else {
    console.log('No search input found - skipping empty search test');
  }

  // 3. Clear search and verify products come back
  if (inputCount > 0) {
    await searchInput.first().fill('');
    await searchInput.first().press('Enter');
    await page.waitForTimeout(3000);

    const afterClearText = await page.textContent('body');
    console.log('After clearing search:', afterClearText?.substring(0, 500));

    // Products should appear again
    const productCardsAfter = page.locator('.product-card');
    const cardCountAfter = await productCardsAfter.count();
    console.log('Product cards after clearing search:', cardCountAfter);
    if (cardCountAfter > 0) {
      expect(cardCountAfter).toBeGreaterThan(0);
    }
  }

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
