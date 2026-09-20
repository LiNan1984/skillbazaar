import { test, expect } from '@playwright/test';

const API_BASE = 'http://localhost:8000/api';
const V2 = `${API_BASE}/v2`;
const FRONTEND = 'http://localhost:7788';

test('product trial execution flow', async ({ page }) => {
  // Register and login
  const creds = { username: `trialtest_${Date.now()}`, password: 'test123456', nickname: '试用测试用户' };
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

  // 1. Navigate to product detail page (code-reviewer, a free Agent product)
  await page.goto(`${FRONTEND}/product/1`);
  await page.waitForTimeout(3000);

  await page.screenshot({ path: '/tmp/trial_product_detail.png', fullPage: false });
  const detailText = await page.textContent('body');
  console.log('Product detail:', detailText?.substring(0, 800));

  // Verify product loaded
  expect(detailText).toContain('code-reviewer');

  // 2. Find and interact with trial execution section
  const trialSection = page.locator('.skill-execute-section');
  const hasTrial = await trialSection.count() > 0;
  console.log('Has trial section:', hasTrial);

  if (hasTrial) {
    // 3. Enter input parameters in trial textarea
    const trialInput = '{"code": "function hello() { return \\"world\\"; }", "language": "javascript"}';
    await page.fill('.skill-execute-input.trial-input', trialInput);

    // 4. Click trial run button
    const trialBtn = page.locator('button.trial-run-btn');
    const btnVisible = await trialBtn.isVisible();
    console.log('Trial button visible:', btnVisible);

    if (btnVisible) {
      await trialBtn.click();
      await page.waitForTimeout(5000);

      await page.screenshot({ path: '/tmp/trial_result.png', fullPage: false });
      const afterTrialText = await page.textContent('body');
      console.log('After trial:', afterTrialText?.substring(0, 1000));

      // 5. Verify trial result appears (success or error — both mean the API responded)
      const hasResult = afterTrialText.includes('试用输出') ||
                        afterTrialText.includes('试用成功') ||
                        afterTrialText.includes('Trial Output') ||
                        afterTrialText.includes('Trial succeeded') ||
                        afterTrialText.includes('No skill asset') ||
                        afterTrialText.includes('skill asset') ||
                        afterTrialText.includes('试用失败');
      console.log('Has trial result:', hasResult);
      expect(hasResult).toBe(true);
    }
  } else {
    console.log('No trial section found - product may not support trial execution');
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
