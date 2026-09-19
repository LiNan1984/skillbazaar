import { chromium } from 'playwright';

const BASE = 'http://localhost:7788';
const browser = await chromium.launch({ headless: true });
const page = await browser.newPage({ viewport: { width: 1280, height: 900 } });

const consoleLogs = [];
const pageErrors = [];
const requestFailures = [];

page.on('console', msg => {
  const text = `[${msg.type()}] ${msg.text()}`;
  consoleLogs.push(text);
  if (msg.type() === 'error') console.error('CONSOLE:', text);
});

page.on('pageerror', err => {
  pageErrors.push(err.message);
  console.error('PAGE ERROR:', err.message);
});

page.on('requestfailed', req => {
  requestFailures.push(`${req.failure()?.errorText || 'failed'}: ${req.url()}`);
});

console.log('Navigating to product detail page...');
await page.goto(`${BASE}/product/106`, { waitUntil: 'networkidle', timeout: 30000 });
await page.waitForTimeout(5000);

console.log('\n=== CONSOLE LOGS ===');
consoleLogs.forEach(l => console.log(l));

console.log('\n=== PAGE ERRORS ===');
pageErrors.forEach(e => console.log(e));

console.log('\n=== REQUEST FAILURES ===');
requestFailures.forEach(f => console.log(f));

// Check what React root contains
const rootInfo = await page.evaluate(() => {
  const root = document.getElementById('root');
  return {
    innerHTML: root?.innerHTML?.substring(0, 500) || 'null',
    children: root?.children?.length || 0,
    hasChildren: root?.children?.length > 0
  };
});
console.log('\n=== ROOT INFO ===');
console.log(rootInfo);

// Check loading state
const loadingInfo = await page.evaluate(() => {
  const skeleton = document.querySelector('.detail-skeleton, .shimmer, .skeleton-line, [class*="loading"]');
  const loadingText = skeleton?.textContent?.substring(0, 200) || 'none';
  return {
    hasSkeleton: !!skeleton,
    loadingText
  };
});
console.log('\n=== LOADING STATE ===');
console.log(loadingInfo);

// Get body text
const bodyText = await page.textContent('body');
console.log(`\nBody text length: ${bodyText.length}`);
console.log(`Body text: "${bodyText?.substring(0, 300)}"`);

await page.screenshot({ path: '/tmp/skbz_detail_full.png', fullPage: true });
console.log('\nScreenshot saved to /tmp/skbz_detail_full.png');

await browser.close();
