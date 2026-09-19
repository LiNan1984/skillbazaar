#!/usr/bin/env node
/**
 * Admin 用户管理 chrome smoke against a local Vite preview (not production).
 * Env: BASE_URL, SCREENSHOT_DIR
 */
const { chromium } = require('playwright')
const fs = require('fs')
const path = require('path')

const BASE_URL = (process.env.BASE_URL || 'http://127.0.0.1:4173').replace(/\/$/, '')
const SCREENSHOT_DIR = process.env.SCREENSHOT_DIR || path.join(__dirname, 'test-results')
const VIEWPORT = { width: 1280, height: 960 }

function fail(msg) {
  console.error(`FAIL: ${msg}`)
  throw new Error(msg)
}

;(async () => {
  fs.mkdirSync(SCREENSHOT_DIR, { recursive: true })
  let browser
  try {
    browser = await chromium.launch({ headless: true })
  } catch (err) {
    const logPath = path.join(SCREENSHOT_DIR, 'playwright-unavailable.log')
    fs.writeFileSync(logPath, `Playwright browser launch failed: ${err.message}\n${err.stack || ''}\n`)
    console.error(fs.readFileSync(logPath, 'utf8'))
    process.exit(2)
  }

  const context = await browser.newContext({ viewport: VIEWPORT, deviceScaleFactor: 1 })
  await context.addInitScript(() => {
    localStorage.setItem('skillbazaar_token', 'smoke-admin-token')
    localStorage.setItem('skillbazaar_role', 'admin')
    localStorage.setItem('skillbazaar_nickname', 'admin')
    localStorage.setItem('skillbazaar_username', 'admin')
    localStorage.setItem('skillbazaar_user_id', 'smoke-admin')
  })
  const page = await context.newPage()
  try {
    await page.goto(`${BASE_URL}/admin`, { waitUntil: 'domcontentloaded', timeout: 20000 })
    await page.waitForSelector('.admin-page, .page-title', { timeout: 10000 })
    const usersTab = page.locator('.admin-tab', { hasText: '用户管理' })
    if ((await usersTab.count()) === 0) fail('用户管理 tab missing')
    await usersTab.first().click()
    await page.waitForTimeout(400)
    const heading = await page.locator('.admin-section-header h2, h2').first().innerText()
    if (!heading.includes('用户管理')) fail(`users heading missing: ${heading}`)
    const body = await page.locator('.admin-users-panel, .admin-page').first().innerText()
    if (!body.includes('封禁') || !body.includes('激活')) {
      fail(`封禁/激活 controls missing from 用户管理 surface: ${body.slice(0, 240)}`)
    }
    const surface = await page.$('.admin-table, .empty-state, .loading-skeleton')
    if (!surface) fail('users table / empty / loading surface missing')
    const shot = path.join(SCREENSHOT_DIR, 'ui-admin-users.png')
    await page.screenshot({ path: shot, fullPage: false })
    console.log(`PASS: 用户管理 chrome visible`)
    console.log(`PASS: wrote ${shot}`)
    await browser.close()
    process.exit(0)
  } catch (err) {
    console.error(err && err.stack ? err.stack : err)
    try {
      await page.screenshot({ path: path.join(SCREENSHOT_DIR, 'ui-admin-users-failure.png'), fullPage: false })
    } catch { /* ignore */ }
    await browser.close().catch(() => {})
    process.exit(1)
  }
})()
