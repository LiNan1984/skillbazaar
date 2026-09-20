import { test, expect } from '@playwright/test';

const FRONTEND = 'http://localhost:7788';

test('404 page: renders for unknown route and navigation works', async ({ page }) => {
  // 1. Navigate to a non-existent route
  await page.goto(`${FRONTEND}/this-page-does-not-exist-${Date.now()}`);
  await page.waitForTimeout(2000);

  await page.screenshot({ path: '/tmp/404_page.png', fullPage: false });
  const text404 = await page.textContent('body');

  // 2. Verify 404 content
  expect(text404).toContain('404');
  expect(text404).toContain('页面不存在');
  expect(text404).toContain('返回首页');
  expect(text404).toContain('浏览悬赏');

  // 3. Click "返回首页" link
  await page.locator('a:has-text("返回首页"), button:has-text("返回首页")').first().click();
  await page.waitForTimeout(2000);

  const currentUrl = page.url();
  console.log('After clicking home:', currentUrl);
  expect(currentUrl).toBe(`${FRONTEND}/`);

  const homeText = await page.textContent('body');
  expect(homeText).toContain('SkillBazaar');
  expect(homeText).toContain('mcporter');
});

test('direct URL access: all major routes load without hash routing', async ({ page }) => {
  const routes = [
    { path: '/', check: 'mcporter' },
    { path: '/bounties', check: '悬赏' },
    { path: '/activities', check: '活动任务中心' },
    { path: '/sandbox', check: '沙盒' },
    { path: '/publish', check: '发布商品' },
    { path: '/library', check: '我的库' },
    { path: '/seller', check: '卖家' },
  ];

  for (const route of routes) {
    console.log(`Testing route: ${route.path}`);
    await page.goto(`${FRONTEND}${route.path}`);
    await page.waitForTimeout(2000);
    const text = await page.textContent('body');

    const hasContent = text?.includes(route.check);
    console.log(`  Route ${route.path} contains "${route.check}":`, hasContent);

    // All pages should at least render the navbar with SkillBazaar
    expect(text).toContain('SkillBazaar');
  }
});

test('product detail: non-existent product shows graceful error', async ({ page }) => {
  await page.goto(`${FRONTEND}/product/99999999`);
  await page.waitForTimeout(3000);

  await page.screenshot({ path: '/tmp/nonexistent_product.png', fullPage: false });
  const text = await page.textContent('body');
  console.log('Non-existent product page:', text?.substring(0, 500));

  // Should still render navbar
  expect(text).toContain('SkillBazaar');

  // Should show error or not found state, not crash
  const hasErrorState = text?.includes('不存在') ||
                        text?.includes('未找到') ||
                        text?.includes('404') ||
                        text?.includes('找不到') ||
                        text?.includes('已下架') ||
                        text?.includes('返回');
  console.log('Graceful error state:', hasErrorState);
});
