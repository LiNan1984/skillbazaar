import { chromium } from 'playwright';
const browser = await chromium.launch({ headless: true });
const page = await browser.newPage();

// Set auth token first
await page.goto('http://localhost:7788', { waitUntil: 'networkidle' });
await page.evaluate(() => {
  localStorage.setItem('skillbazaar_token', 'test');
  localStorage.setItem('skillbazaar_user_id', 'test');
});

await page.goto('http://localhost:7788/product/106', { waitUntil: 'networkidle', timeout: 30000 });
await page.waitForTimeout(5000);

// Get the page HTML
const html = await page.content();

// Check for loading indicators
const hasSkeleton = html.includes('skeleton') || html.includes('shimmer') || html.includes('loading');
const hasError = html.includes('error') || html.includes('Error') || html.includes('404') || html.includes('Not Found');
const hasProductName = html.includes('mcporter');
const hasProductDesc = html.includes('mcporter CLI') || html.includes('MCP');

console.log('Has skeleton/loading:', hasSkeleton);
console.log('Has error text:', hasError);
console.log('Has product name "mcporter":', hasProductName);
console.log('Has product description:', hasProductDesc);
console.log('Total HTML length:', html.length);

// Get visible text
const bodyText = await page.textContent('body');
console.log('Body text length:', bodyText.length);
console.log('Body text preview:', bodyText.substring(0, 500));

// Check React root
const rootContent = await page.$eval('#root', el => el.innerHTML.length);
console.log('React root innerHTML length:', rootContent);

// Check for any error boundaries
const errorText = await page.$eval('.error-boundary, [class*="error"]', el => el.textContent).catch(() => 'none');
console.log('Error boundary text:', errorText);

await page.screenshot({ path: '/tmp/skbz_detail_debug.png', fullPage: true });

// Check network requests
const requests = [];
page.on('request', req => {
  if (req.url().includes('product') || req.url().includes('api')) {
    requests.push(req.url());
  }
});
await page.reload({ waitUntil: 'networkidle' });
await page.waitForTimeout(5000);
console.log('\nAPI requests:', requests);

await browser.close();
