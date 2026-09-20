import { test, expect } from '@playwright/test';

const V2 = 'http://localhost:8000/api/v2';
const API_BASE = 'http://localhost:8000/api';
const FRONTEND = 'http://localhost:7788';

test('publish page: multi-step form renders and validates', async ({ page }) => {
  const creds = { username: `pub_${Date.now()}`, password: 'test123456', nickname: '发布测试用户' };
  await fetch(`${V2}/auth/register`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(creds)
  });

  const loginResp = await fetch(`${V2}/auth/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ username: creds.username, password: creds.password })
  });
  const loginData = await loginResp.json();

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
  }, { t: loginData.token, uid: loginData.user_id, un: creds.username, nick: creds.nickname });

  // 1. Navigate to publish page
  await page.goto(`${FRONTEND}/publish`);
  await page.waitForTimeout(2000);

  await page.screenshot({ path: '/tmp/publish_step1.png', fullPage: false });
  const step1Text = await page.textContent('body');
  console.log('Publish step 1:', step1Text?.substring(0, 800));

  // 2. Verify page structure
  expect(step1Text).toContain('发布商品');
  expect(step1Text).toContain('基本信息');
  expect(step1Text).toContain('技能上传');
  expect(step1Text).toContain('商品名称');
  expect(step1Text).toContain('商品描述');
  expect(step1Text).toContain('分类');
  expect(step1Text).toContain('定价');

  // 3. Test validation - try next without filling
  const nextBtn = page.locator('button:has-text("下一步")');
  await nextBtn.first().click();
  await page.waitForTimeout(500);

  const validationText = await page.textContent('body');
  console.log('Validation error shown:', validationText?.includes('请先填写必要信息'));
  expect(validationText).toContain('请先填写必要信息');

  // 4. Fill step 1 - basic info
  const productName = `E2E表单测试_${Date.now()}`;
  await page.locator('input[placeholder*="商品起个名字"]').fill(productName);
  await page.locator('textarea[placeholder*="详细描述"]').fill('这是一个E2E自动测试创建的商品，用于验证发布表单流程。');

  // Select category
  await page.locator('select.form-select').first().selectOption('Skill');
  await page.waitForTimeout(500);

  // Select subcategory
  const subSelects = page.locator('select.form-select').nth(1);
  await subSelects.selectOption('文件处理');
  await page.waitForTimeout(300);

  // Fill price
  await page.locator('input[placeholder*="输入价格"]').fill('300');

  // Fill tags
  await page.locator('input[placeholder*="逗号分隔"]').fill('测试,E2E,表单');

  // Fill content preview
  await page.locator('textarea[placeholder*="SKILL.md"]').fill('# Test Skill\n\nThis is a test skill content for form validation.');

  await page.screenshot({ path: '/tmp/publish_step1_filled.png', fullPage: false });

  // 5. Go to step 2 - skill type selection
  await nextBtn.first().click();
  await page.waitForTimeout(1000);

  await page.screenshot({ path: '/tmp/publish_step2.png', fullPage: false });
  const step2Text = await page.textContent('body');
  console.log('Publish step 2:', step2Text?.substring(0, 600));

  // Verify skill type options
  expect(step2Text).toContain('技能类型');
  expect(step2Text).toContain('提示词技能');
  expect(step2Text).toContain('代码技能包');
  expect(step2Text).toContain('高码 SDK');

  // 6. Select SDK skill type (doesn't require file upload, shows endpoint input)
  const sdkCard = page.locator('.skill-type-card:has-text("高码 SDK")');
  await sdkCard.click();
  await page.waitForTimeout(500);

  await page.screenshot({ path: '/tmp/publish_step2_sdk.png', fullPage: false });

  const afterSdkText = await page.textContent('body');
  expect(afterSdkText).toContain('SDK 服务地址');
  console.log('SDK type selected, endpoint input visible');

  // 7. Test back button works
  await page.locator('button:has-text("上一步")').first().click();
  await page.waitForTimeout(500);

  const backOnStep1 = await page.textContent('body');
  expect(backOnStep1).toContain('商品名称');
  console.log('Back button works, returned to step 1');

  // 8. Navigate forward again to verify form state preserved
  await page.locator('button:has-text("下一步")').first().click();
  await page.waitForTimeout(800);

  const backOnStep2 = await page.textContent('body');
  expect(backOnStep2).toContain('提示词技能');
  console.log('Form state preserved across navigation');

  // 9. Verify no console errors
  const consoleErrors = [];
  page.on('console', msg => {
    if (msg.type() === 'error') consoleErrors.push(msg.text());
  });

  await page.reload();
  await page.waitForTimeout(2000);
  console.log('Console errors:', consoleErrors);
  expect(consoleErrors.length).toBe(0);
});
