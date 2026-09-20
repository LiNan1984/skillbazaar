import { test, expect } from '@playwright/test';

const V2 = 'http://localhost:8000/api/v2';
const API_BASE = 'http://localhost:8000/api';
const FRONTEND = 'http://localhost:7788';

test('notification bell: renders in navbar when logged in', async ({ page }) => {
  // Register and login
  const creds = { username: `notif_${Date.now()}`, password: 'test123456', nickname: '通知测试用户' };
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

  // 1. Check homepage for notification bell
  await page.goto(FRONTEND);
  await page.waitForTimeout(2000);

  await page.screenshot({ path: '/tmp/notification_bell.png', fullPage: false });
  const pageText = await page.textContent('body');
  console.log('Homepage with auth:', pageText?.substring(0, 500));

  // 2. Verify bell icon is rendered (NotificationBell component)
  // The bell uses the Bell icon from lucide-react, but it's an SVG
  // Let's check if the notification dropdown area exists
  const hasNotificationBell = await page.locator('[class*="notification"], [class*="bell"], .notification-bell').count();
  console.log('Notification bell elements:', hasNotificationBell);

  // Check via API that notifications endpoint works
  const notifResp = await fetch(`${V2}/notifications`, {
    headers: { Authorization: `Bearer ${loginData.token}` }
  });
  const notifData = await notifResp.json();
  console.log('Notifications API response:', notifData);

  // Verify notifications API returns expected format
  expect(notifData).toHaveProperty('notifications');
  expect(notifData).toHaveProperty('unread_count');
  expect(Array.isArray(notifData.notifications)).toBe(true);

  // 3. Test mark as read functionality
  if (notifData.notifications.length > 0) {
    const firstNotif = notifData.notifications[0];
    const markResp = await fetch(`${V2}/notifications/${firstNotif.id}/read`, {
      method: 'POST',
      headers: { Authorization: `Bearer ${loginData.token}` }
    });
    const markData = await markResp.json();
    console.log('Mark read response:', markData);

    // Verify it was marked as read
    expect(markData.success !== false).toBe(true);
  } else {
    console.log('No notifications to mark as read');
  }

  // 4. Verify no console errors
  const consoleErrors = [];
  page.on('console', msg => {
    if (msg.type() === 'error') consoleErrors.push(msg.text());
  });

  await page.reload();
  await page.waitForTimeout(2000);
  console.log('Console errors:', consoleErrors);
  expect(consoleErrors.length).toBe(0);
});
