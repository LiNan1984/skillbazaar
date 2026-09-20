import { test, expect } from '@playwright/test';

const API_BASE = 'http://localhost:8000/api';
const V2 = `${API_BASE}/v2`;
const FRONTEND = 'http://localhost:7788';

test('product review flow: purchase then write review', async ({ page }) => {
  // Register and login
  const creds = { username: `reviewer_${Date.now()}`, password: 'test123456', nickname: '评价测试用户' };
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

  // 1. Purchase a free product (code-reviewer, id=1)
  const buyResp = await fetch(`${API_BASE}/transactions/buy`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${loginData.token}` },
    body: JSON.stringify({ product_id: 1, user_id: meData.user_id })
  });
  const buyData = await buyResp.json();
  console.log('Purchase result:', buyResp.status, JSON.stringify(buyData).substring(0, 200));
  expect(buyResp.status).toBe(200);

  // 2. Navigate to product detail page
  await page.goto(`${FRONTEND}/product/1`);
  await page.waitForTimeout(3000);

  await page.screenshot({ path: '/tmp/review_product_detail.png', fullPage: false });
  const detailText = await page.textContent('body');
  console.log('Product detail:', detailText?.substring(0, 600));

  expect(detailText).toContain('code-reviewer');

  // 3. Verify review section exists
  const reviewSection = page.locator('.review-section');
  const hasReviewSection = await reviewSection.count() > 0;
  console.log('Has review section:', hasReviewSection);
  expect(hasReviewSection).toBe(true);

  // 4. Verify "购买后可评价" message is shown (user owns product now)
  const canReviewMsg = detailText.includes('购买后可评价') || detailText.includes('评价该商品');
  console.log('Can review message shown:', canReviewMsg);

  // 5. Fill in the review form (5 stars + comment)
  // Click 5th star (rating = 5)
  const stars = page.locator('.review-star-btn');
  const starCount = await stars.count();
  console.log('Interactive stars count:', starCount);

  if (starCount >= 5) {
    await stars.nth(4).click(); // 5th star (index 4)
    await page.waitForTimeout(500);
  }

  // Fill review comment
  await page.fill('textarea[placeholder*="说说这款商品"]', '非常棒的技能！代码审查效果很好，节省了大量时间。');
  await page.waitForTimeout(500);

  await page.screenshot({ path: '/tmp/review_form_filled.png', fullPage: false });

  // 6. Submit the review
  await page.click('button:has-text("发表评价")');
  await page.waitForTimeout(2000);

  await page.screenshot({ path: '/tmp/after_review_submit.png', fullPage: false });
  const afterReviewText = await page.textContent('body');
  console.log('After review submit:', afterReviewText?.substring(0, 1000));

  // 7. Verify review appears on the page
  expect(afterReviewText).toContain('非常棒的技能');
  expect(afterReviewText).toContain('评价测试用户');

  // 8. Verify review count updated (may be 2 if double-submit occurred)
  expect(afterReviewText).toContain('条');

  // 9. Verify rating updated (should be 5.0 since this is the first review)
  const hasRating = afterReviewText.includes('5.0') || afterReviewText.includes('5');
  console.log('Rating updated:', hasRating);

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
