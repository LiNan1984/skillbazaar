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
  const failText = `${req.failure()?.errorText || 'failed'}: ${req.url()}`;
  requestFailures.push(failText);
  console.error('REQUEST FAILED:', failText);
});

// Track response failures (500s, 403s)
const responseErrors = [];
page.on('response', async (resp) => {
  if (resp.status() >= 400) {
    const url = resp.url();
    const errorText = await resp.text().catch(() => '');
    responseErrors.push(`${resp.status()}: ${url} -> ${errorText.substring(0, 200)}`);
    console.error(`RESPONSE ${resp.status()}: ${url} -> ${errorText.substring(0, 200)}`);
  }
});

// Login first
const tokenResp = await page.request.post('http://localhost:8000/api/v2/auth/login', {
  data: { username: 't1q8ufvwa', password: 'TestPass123!' }
});
const tokenData = await tokenResp.json();
const token = tokenData.token;

await page.goto(`${BASE}/login`, { waitUntil: 'networkidle', timeout: 30000 });
await page.evaluate((t) => {
  localStorage.setItem('skillbazaar_token', t);
  localStorage.setItem('skillbazaar_user_id', 'da6fbee8-4d1c-4c7d-98a3-f16c9e9e32c4');
}, token);
await page.goto(`${BASE}/sandbox`, { waitUntil: 'networkidle', timeout: 30000 });
await page.waitForTimeout(3000);

console.log('\n=== CONSOLE ERRORS ===');
consoleLogs.filter(l => l.includes('ERROR') || l.includes('500') || l.includes('403')).forEach(l => console.log(l));

console.log('\n=== RESPONSE ERRORS (500/403) ===');
responseErrors.forEach(e => console.log(e));

console.log('\n=== PAGE ERRORS ===');
pageErrors.forEach(e => console.log(e));

const bodyText = await page.textContent('body');
console.log(`\nSandbox page content: ${bodyText?.substring(0, 500)}`);

await page.screenshot({ path: '/tmp/skbz_sandbox_detail.png', fullPage: true });
console.log('\nScreenshot saved to /tmp/skbz_sandbox_detail.png');

await browser.close();
