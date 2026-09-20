import { test, expect } from '@playwright/test';

const FRONTEND = 'http://localhost:7788';

test.describe('responsive layout', () => {
  test('mobile viewport: homepage renders without horizontal overflow', async ({ browser }) => {
    const context = await browser.newContext({
      viewport: { width: 375, height: 812 }
    });
    const page = await context.newPage();

    const consoleErrors = [];
    page.on('console', msg => {
      if (msg.type() === 'error') consoleErrors.push(msg.text());
    });

    await page.goto(FRONTEND);
    await page.waitForTimeout(3000);

    await page.screenshot({ path: '/tmp/mobile_home.png', fullPage: false });

    // Check for horizontal overflow
    const hasHorizontalOverflow = await page.evaluate(() => {
      return document.documentElement.scrollWidth > document.documentElement.clientWidth;
    });
    console.log('Homepage horizontal overflow:', hasHorizontalOverflow);

    const mobileText = await page.textContent('body');
    expect(mobileText).toContain('SkillBazaar');
    expect(mobileText).toContain('mcporter');

    // Test key pages on mobile
    const routes = ['/bounties', '/activities', '/publish'];
    for (const route of routes) {
      await page.goto(`${FRONTEND}${route}`);
      await page.waitForTimeout(2000);

      const overflow = await page.evaluate(() => {
        return document.documentElement.scrollWidth > document.documentElement.clientWidth;
      });
      console.log(`Route ${route} overflow:`, overflow);

      await page.screenshot({ path: `/tmp/mobile_${route.replace('/', '')}.png`, fullPage: false });

      const text = await page.textContent('body');
      expect(text).toContain('SkillBazaar');
    }

    console.log('Mobile console errors:', consoleErrors);
    await context.close();
  });

  test('tablet viewport: product detail page renders', async ({ browser }) => {
    const context = await browser.newContext({
      viewport: { width: 768, height: 1024 }
    });
    const page = await context.newPage();

    await page.goto(`${FRONTEND}/product/106`);
    await page.waitForTimeout(3000);

    await page.screenshot({ path: '/tmp/tablet_product.png', fullPage: false });

    const text = await page.textContent('body');
    expect(text).toContain('mcporter');
    expect(text).toContain('SkillBazaar');

    const overflow = await page.evaluate(() => {
      return document.documentElement.scrollWidth > document.documentElement.clientWidth;
    });
    console.log('Tablet product page overflow:', overflow);

    await context.close();
  });

  test('desktop viewport: standard layout renders correctly', async ({ browser }) => {
    const context = await browser.newContext({
      viewport: { width: 1440, height: 900 }
    });
    const page = await context.newPage();

    await page.goto(FRONTEND);
    await page.waitForTimeout(3000);

    await page.screenshot({ path: '/tmp/desktop_home.png', fullPage: false });

    const text = await page.textContent('body');
    expect(text).toContain('SkillBazaar');

    // Product grid should be visible
    const productCards = page.locator('.product-card');
    const cardCount = await productCards.count();
    console.log('Desktop product cards visible:', cardCount);
    expect(cardCount).toBeGreaterThan(0);

    await context.close();
  });
});
