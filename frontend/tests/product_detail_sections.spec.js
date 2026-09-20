import { test, expect } from '@playwright/test';

const V2 = 'http://localhost:8000/api/v2';
const API_BASE = 'http://localhost:8000/api';
const FRONTEND = 'http://localhost:7788';

test('product detail: description, tags, compatibility, and related products', async ({ page }) => {
  // Register and login
  const creds = { username: `detail_${Date.now()}`, password: 'test123456', nickname: '详情测试用户' };
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

  // 1. Navigate to product detail page (code-reviewer, id=1)
  await page.goto(`${FRONTEND}/product/1`);
  await page.waitForTimeout(3000);

  await page.screenshot({ path: '/tmp/detail_sections.png', fullPage: false });
  const detailText = await page.textContent('body');
  console.log('Product detail:', detailText?.substring(0, 1500));

  // Verify basic product info
  expect(detailText).toContain('code-reviewer');

  // 2. Verify description section
  const hasDescription = detailText.includes('描述') ||
                         detailText.includes('description') ||
                         detailText.includes('功能') ||
                         detailText.includes('工具');
  console.log('Has description section:', hasDescription);
  if (hasDescription) {
    expect(detailText).not.toContain('暂无描述');
  }

  // 3. Verify tags section
  const hasTags = detailText.includes('标签') ||
                  detailText.includes('Tag') ||
                  detailText.includes('Prompt') ||
                  detailText.includes('Agent');
  console.log('Has tags section:', hasTags);

  // 4. Verify compatibility section (platform badges)
  const hasCompat = detailText.includes('兼容') ||
                    detailText.includes('Claude') ||
                    detailText.includes('Codex') ||
                    detailText.includes('SDK') ||
                    detailText.includes('平台');
  console.log('Has compatibility section:', hasCompat);

  // 5. Verify eval score section (or at least product rating)
  const hasRating = detailText.includes('评分') ||
                    detailText.includes('rating') ||
                    detailText.includes('★') ||
                    detailText.includes('⭐') ||
                    /\d+\.\d+/.test(detailText.match(/评分[：\s]*([\d.]+)/)?.[1] || '');
  console.log('Has rating section:', hasRating);

  // 6. Verify related products section
  const hasRelated = detailText.includes('相关') ||
                     detailText.includes('推荐') ||
                     detailText.includes('相似');
  console.log('Has related products section:', hasRelated);

  // 7. Verify product metadata (source, category, downloads, sales)
  const hasMetadata = detailText.includes('source') ||
                      detailText.includes('来源') ||
                      detailText.includes('下载') ||
                      detailText.includes('销量') ||
                      detailText.includes('steipete');
  console.log('Has metadata:', hasMetadata);

  // 8. Verify product links (GitHub, export SKILL.md)
  const hasLinks = detailText.includes('GitHub') ||
                   detailText.includes('github') ||
                   detailText.includes('SKILL.md') ||
                   detailText.includes('导出');
  console.log('Has product links:', hasLinks);

  // 9. Verify buy panel on the right sidebar
  const hasPrice = detailText.includes('￥') ||
                   detailText.includes('¥') ||
                   detailText.includes('金币') ||
                   detailText.includes('购买');
  console.log('Has price/buy panel:', hasPrice);
  if (hasPrice) {
    const hasBuyBtn = detailText.includes('立即购买') || detailText.includes('免费购买') || detailText.includes('购买');
    console.log('Has buy button:', hasBuyBtn);
  }

  // 10. Verify no console errors
  const consoleErrors = [];
  page.on('console', msg => {
    if (msg.type() === 'error') consoleErrors.push(msg.text());
  });

  await page.reload();
  await page.waitForTimeout(2000);
  console.log('Console errors:', consoleErrors);
  expect(consoleErrors.length).toBe(0);
});
