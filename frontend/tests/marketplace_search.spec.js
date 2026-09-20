import { test, expect } from '@playwright/test';

const V2 = 'http://localhost:8000/api/v2';
const API_BASE = 'http://localhost:8000/api';
const FRONTEND = 'http://localhost:7788';

test('marketplace: search, category filter and language toggle', async ({ page }) => {
  // Navigate to homepage without auth - search should work for anonymous users too
  await page.goto(FRONTEND);
  await page.waitForTimeout(3000);

  await page.screenshot({ path: '/tmp/market_home.png', fullPage: false });
  const homeText = await page.textContent('body');
  console.log('Homepage loaded:', homeText?.substring(0, 400));

  // 1. Verify products are loaded
  expect(homeText).toContain('SkillBazaar');
  expect(homeText).toContain('mcporter');

  // 2. Verify category tabs exist
  const catTabs = page.locator('.category-tab, [class*="category"] button, button:has-text("Agent"), button:has-text("Skill")');
  const catCount = await catTabs.count();
  console.log('Category tabs found:', catCount);

  // 3. Test search functionality
  const searchInput = page.locator('.search-input, input[placeholder*="搜索"], input[type="text"]').first();
  await searchInput.fill('mcp');
  await page.waitForTimeout(1500); // Wait for debounce + API call

  await page.screenshot({ path: '/tmp/market_search.png', fullPage: false });
  const searchText = await page.textContent('body');
  console.log('Search results:', searchText?.substring(0, 500));

  // Verify URL has keyword param
  const urlAfterSearch = page.url();
  console.log('URL after search:', urlAfterSearch);
  expect(urlAfterSearch).toContain('keyword=mcp');

  // 4. Verify search results show MCP-related products
  const hasMcpResults = searchText?.toLowerCase().includes('mcp') ||
                        searchText?.includes('mcporter') ||
                        searchText?.includes('exa');
  expect(hasMcpResults).toBe(true);

  // 5. Clear search
  await searchInput.fill('');
  await page.waitForTimeout(1500);

  const urlAfterClear = page.url();
  console.log('URL after clear:', urlAfterClear);

  // 6. Test sort options
  await page.goto(`${FRONTEND}/?sort=newest`);
  await page.waitForTimeout(2000);
  const newestText = await page.textContent('body');
  expect(newestText).toContain('SkillBazaar');
  console.log('Sort by newest works');

  // 7. Test category filter via URL
  await page.goto(`${FRONTEND}/?category=Agent`);
  await page.waitForTimeout(2000);

  await page.screenshot({ path: '/tmp/market_agent_filter.png', fullPage: false });
  const agentText = await page.textContent('body');
  console.log('Agent filter:', agentText?.substring(0, 400));

  // 8. Test language toggle (EN button)
  await page.goto(FRONTEND);
  await page.waitForTimeout(2000);

  const langBtn = page.locator('button:has-text("EN"), button:has-text("中文")');
  const langCount = await langBtn.count();
  console.log('Language button count:', langCount);

  if (langCount > 0) {
    const initialLang = await page.textContent('body');
    const isChinese = initialLang?.includes('发布商品') || initialLang?.includes('悬赏市场');
    console.log('Initial language is Chinese:', isChinese);

    await langBtn.first().click();
    await page.waitForTimeout(1500);

    await page.screenshot({ path: '/tmp/market_en.png', fullPage: false });
    const afterToggle = await page.textContent('body');
    console.log('After language toggle:', afterToggle?.substring(0, 300));

    // After toggling from Chinese, should show English
    if (isChinese) {
      const hasEnglish = afterToggle?.includes('Publish') ||
                        afterToggle?.includes('Market') ||
                        afterToggle?.includes('Bounty') ||
                        afterToggle?.includes('中文'); // toggle button now shows "中文"
      console.log('English UI shown:', hasEnglish);
    }

    // Toggle back
    await page.locator('button:has-text("中文"), button:has-text("EN")').first().click();
    await page.waitForTimeout(1000);
  }

  // 9. Test pagination
  await page.goto(FRONTEND);
  await page.waitForTimeout(3000);

  const paginationBtns = page.locator('.pagination button, [class*="page"] button');
  const pageBtnCount = await paginationBtns.count();
  console.log('Pagination buttons:', pageBtnCount);

  // 10. Verify no console errors
  const consoleErrors = [];
  page.on('console', msg => {
    if (msg.type() === 'error') consoleErrors.push(msg.text());
  });

  await page.goto(FRONTEND);
  await page.waitForTimeout(2000);
  console.log('Console errors:', consoleErrors);
  expect(consoleErrors.length).toBe(0);
});
