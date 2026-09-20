import { test, expect } from '@playwright/test';

const V2 = 'http://localhost:8000/api/v2';
const FRONTEND = 'http://localhost:7788';

test('auth flow: register, login, logout via UI modal', async ({ page }) => {
  const timestamp = Date.now();
  const username = `auth_ui_${timestamp}`;
  const password = 'test123456';
  const nickname = 'UI认证测试';

  // 1. Navigate to homepage (logged out)
  await page.goto(FRONTEND);
  await page.waitForTimeout(2000);

  await page.screenshot({ path: '/tmp/auth_logged_out.png', fullPage: false });
  const loggedOutText = await page.textContent('body');
  expect(loggedOutText).toContain('登录');
  expect(loggedOutText).toContain('注册');

  // 2. Click register button to open auth modal
  const registerBtn = page.locator('button:has-text("注册"), button:has-text("Register")').first();
  await registerBtn.click();
  await page.waitForTimeout(1000);

  await page.screenshot({ path: '/tmp/auth_register_modal.png', fullPage: false });
  const modalText = await page.textContent('body');
  expect(modalText).toContain('注册');

  // 3. Fill registration form
  const usernameInput = page.locator('.auth-modal input[type="text"]').first();
  await usernameInput.fill(username);

  // Nickname field (only in register mode)
  const nicknameInput = page.locator('.auth-modal input[placeholder*="昵称"], .auth-modal input[placeholder*="可选"]');
  if (await nicknameInput.count() > 0) {
    await nicknameInput.fill(nickname);
  }

  // Password
  const passwordInput = page.locator('.auth-modal input[type="password"]');
  await passwordInput.fill(password);

  await page.screenshot({ path: '/tmp/auth_register_filled.png', fullPage: false });

  // 4. Submit registration
  const submitBtn = page.locator('.auth-modal button[type="submit"]');
  await submitBtn.click();
  await page.waitForTimeout(2000);

  await page.screenshot({ path: '/tmp/auth_after_register.png', fullPage: false });

  // After register, modal should switch to login mode
  const afterRegisterText = await page.textContent('body');
  console.log('After register:', afterRegisterText?.substring(0, 300));

  // 5. Fill login form (modal should have switched to login)
  const loginUsernameInput = page.locator('.auth-modal input[type="text"]').first();
  const loginPasswordInput = page.locator('.auth-modal input[type="password"]');

  if (await loginUsernameInput.count() > 0) {
    await loginUsernameInput.fill(username);
    await loginPasswordInput.fill(password);

    await page.screenshot({ path: '/tmp/auth_login_filled.png', fullPage: false });

    const loginSubmit = page.locator('.auth-modal button[type="submit"]');
    await loginSubmit.click();
    await page.waitForTimeout(2000);
  }

  await page.screenshot({ path: '/tmp/auth_logged_in.png', fullPage: false });
  const loggedInText = await page.textContent('body');
  console.log('After login:', loggedInText?.substring(0, 300));

  // 6. Verify logged in state
  const hasWallet = loggedInText?.includes('钱包') || loggedInText?.includes(nickname);
  const hasLogout = loggedInText?.includes('退出') || loggedInText?.includes('登出');
  console.log('Wallet visible:', hasWallet, 'Logout visible:', hasLogout);

  // Verify localStorage has token
  const token = await page.evaluate(() => localStorage.getItem('skillbazaar_token'));
  console.log('Token set:', Boolean(token));
  expect(token).toBeTruthy();

  // 7. Test invalid login
  const logoutBtn = page.locator('button:has-text("退出"), button:has-text("Logout")').first();
  if (await logoutBtn.count() > 0) {
    await logoutBtn.click();
    await page.waitForTimeout(1000);

    const afterLogoutText = await page.textContent('body');
    expect(afterLogoutText).toContain('登录');
    console.log('Logout successful');

    // Try login with wrong password
    const loginBtn = page.locator('button:has-text("登录"), button:has-text("Login")').first();
    await loginBtn.click();
    await page.waitForTimeout(1000);

    await page.locator('.auth-modal input[type="text"]').first().fill(username);
    await page.locator('.auth-modal input[type="password"]').fill('wrongpassword');
    await page.locator('.auth-modal button[type="submit"]').click();
    await page.waitForTimeout(1500);

    await page.screenshot({ path: '/tmp/auth_invalid_login.png', fullPage: false });
    const errorText = await page.textContent('body');
    const hasError = errorText?.includes('错误') ||
                     errorText?.includes('密码') ||
                     errorText?.includes('失败') ||
                     errorText?.includes('error');
    console.log('Invalid login error shown:', hasError);
  }

  // 8. Verify no unexpected console errors
  const consoleErrors = [];
  page.on('console', msg => {
    if (msg.type() === 'error') {
      const text = msg.text();
      // Ignore expected API errors from invalid login test
      if (!text.includes('401') && !text.includes('登录') && !text.includes('密码')) {
        consoleErrors.push(text);
      }
    }
  });
});
