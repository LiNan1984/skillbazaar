#!/usr/bin/env node
/**
 * Local UI smoke for the Vite-built SkillBazaar Human Web marketplace.
 * Targets a local preview (default http://127.0.0.1:4173), never production.
 *
 * Env:
 *   BASE_URL         preview origin (default http://127.0.0.1:4173)
 *   SCREENSHOT_DIR   directory for ui-home.png / ui-bounties.png / ui-chat.png
 */
const { chromium } = require('playwright')
const fs = require('fs')
const path = require('path')

const BASE_URL = (process.env.BASE_URL || 'http://127.0.0.1:4173').replace(/\/$/, '')
const SCREENSHOT_DIR = process.env.SCREENSHOT_DIR || path.join(__dirname, 'test-results')
const VIEWPORT = { width: 1280, height: 960 }
const SEARCH_KEYWORD = 'quant'

function fail(message) {
  console.error(`FAIL: ${message}`)
  throw new Error(message)
}

function ok(message) {
  console.log(`PASS: ${message}`)
}

async function gotoReady(page, urlPath) {
  const response = await page.goto(`${BASE_URL}${urlPath}`, {
    waitUntil: 'domcontentloaded',
    timeout: 20000,
  })
  if (!response) fail(`no response for ${urlPath}`)
  const status = response.status()
  if (status >= 400) fail(`${urlPath} returned HTTP ${status}`)
  await page.waitForSelector('.navbar', { timeout: 10000 })
  await page.waitForTimeout(500)
}

async function measurePainted(page) {
  return page.evaluate(() => {
    const vw = window.innerWidth
    const vh = window.innerHeight
    const step = 24
    let total = 0
    let hit = 0
    const chromeHits = {}
    const selector =
      '.navbar, .hero-banner, .hero-content, .hero-advantages, .hero-advantage-card, .hero-stats, .category-tabs-container, .category-tab, .sort-bar, .catalog-heading, .product-grid, .product-card, .empty-state, .bounty-page, .bounty-header, .bounty-filters, .bounty-card, .bounty-list, .loading-skeleton, .skeleton-card, .detail-page, .detail-main, .chat-panel, .floating-assistant, .page-shell'
    for (let y = 12; y < vh - 12; y += step) {
      for (let x = 12; x < vw - 12; x += step) {
        total += 1
        const el = document.elementFromPoint(x, y)
        if (!el) continue
        const meaningful = el.closest(selector)
        if (meaningful) {
          hit += 1
          const key = (meaningful.className || meaningful.tagName).toString().split(' ')[0]
          chromeHits[key] = (chromeHits[key] || 0) + 1
        }
      }
    }
    const app = document.querySelector('.app')
    const appRect = app ? app.getBoundingClientRect() : { width: 0, height: 0, top: 0, bottom: 0 }
    return {
      total,
      hit,
      hitRatio: total ? hit / total : 0,
      chromeHits,
      vw,
      vh,
      appFill: vw * vh ? (appRect.width * Math.min(appRect.height, vh)) / (vw * vh) : 0,
      appHeight: appRect.height,
    }
  })
}

async function assertFilled(page, label) {
  const stats = await measurePainted(page)
  console.log(`PAINT[${label}]: hitRatio=${stats.hitRatio.toFixed(3)} appFill=${stats.appFill.toFixed(3)} hits=${JSON.stringify(stats.chromeHits)}`)
  if (stats.vw !== VIEWPORT.width || stats.vh !== VIEWPORT.height) {
    fail(`${label} viewport is ${stats.vw}x${stats.vh}, expected ${VIEWPORT.width}x${VIEWPORT.height}`)
  }
  if (stats.appFill < 0.9) {
    fail(`${label} .app does not fill the viewport (appFill=${stats.appFill.toFixed(3)})`)
  }
  if (stats.hitRatio < 0.4) {
    fail(`${label} painted chrome is too sparse (hitRatio=${stats.hitRatio.toFixed(3)} < 0.4)`)
  }
  return stats
}

async function assertPngSize(filePath) {
  const buf = fs.readFileSync(filePath)
  if (buf[0] !== 0x89 || buf[1] !== 0x50) fail(`${filePath} is not a PNG`)
  const width = buf.readUInt32BE(16)
  const height = buf.readUInt32BE(20)
  console.log(`PNG ${path.basename(filePath)}: ${width}x${height}`)
  if (width !== VIEWPORT.width || height !== VIEWPORT.height) {
    fail(`${filePath} is ${width}x${height}, expected ${VIEWPORT.width}x${VIEWPORT.height}`)
  }
}

;(async () => {
  fs.mkdirSync(SCREENSHOT_DIR, { recursive: true })
  console.log(`SkillBazaar UI smoke against ${BASE_URL}`)
  console.log(`Screenshots → ${SCREENSHOT_DIR}`)

  let browser
  try {
    browser = await chromium.launch({ headless: true })
  } catch (err) {
    const logPath = path.join(SCREENSHOT_DIR, 'playwright-unavailable.log')
    const detail = `Playwright browser launch failed: ${err.message}\n${err.stack || ''}\n`
    fs.writeFileSync(logPath, detail)
    console.error(detail)
    process.exit(2)
  }

  const pageErrors = []
  const context = await browser.newContext({
    viewport: VIEWPORT,
    deviceScaleFactor: 1,
  })
  const page = await context.newPage()
  page.on('pageerror', (err) => {
    pageErrors.push(String(err && err.message ? err.message : err))
  })

  try {
    await gotoReady(page, '/')

    const title = await page.title()
    console.log(`Title: ${title}`)
    if (!/SkillBazaar/i.test(title)) fail(`document title does not identify SkillBazaar: ${title}`)
    ok('title identifies SkillBazaar')

    const nav = await page.$('.navbar')
    if (!nav) fail('navbar missing')
    ok('navbar exists')

    const search = await page.$('.navbar-search .search-input, .search-input')
    if (!search) fail('search input missing')
    ok('search input exists')

    const tabLabels = await page.$$eval('.category-tab', (els) => els.map((el) => el.textContent.trim()))
    console.log(`Category tabs: ${JSON.stringify(tabLabels)}`)
    for (const label of ['Agent', 'Skill', 'Cron', 'Workflow']) {
      if (!tabLabels.some((t) => t.includes(label))) fail(`category tab "${label}" missing (have ${tabLabels.join(', ')})`)
    }
    ok('category tabs Agent / Skill / Cron / Workflow exist')

    const assistant = await page.$('.floating-assistant')
    if (!assistant) fail('floating assistant missing')
    ok('floating assistant exists')

    const keepLabels = await page.evaluate(() => document.body.innerText)
    for (const label of ['悬赏', '我的库', '发布']) {
      if (!keepLabels.includes(label)) fail(`chrome is missing "${label}"`)
    }
    ok('悬赏 / 我的库 / 发布 remain in chrome')

    await page.waitForSelector('.product-grid, .empty-state, .product-card', { timeout: 12000 })
    const catalogInView = await page.evaluate(() => {
      const el = document.querySelector('.product-grid, .home-page .empty-state, .product-card')
      if (!el) return { ok: false }
      const r = el.getBoundingClientRect()
      return { ok: r.top < window.innerHeight - 80 && r.bottom > 120, top: r.top, bottom: r.bottom, vh: window.innerHeight }
    })
    console.log(`Catalog in viewport: ${JSON.stringify(catalogInView)}`)
    if (!catalogInView.ok) fail('home catalog grid/empty state is not in the primary viewport')
    ok('home catalog occupies the primary viewport')

    await assertFilled(page, 'home')
    const homePath = path.join(SCREENSHOT_DIR, 'ui-home.png')
    await page.screenshot({ path: homePath, fullPage: false })
    await assertPngSize(homePath)
    ok(`wrote ${homePath}`)

    const productCard = await page.$('.product-card:not(.skeleton)')
    if (productCard) {
      await productCard.click()
      await page.waitForTimeout(600)
      if (!page.url().includes('/product/')) fail('product card click did not open product detail')
      await page.waitForSelector('.detail-page', { timeout: 8000 })
      ok('product card opened product detail')
      await page.goto(`${BASE_URL}/`, { waitUntil: 'domcontentloaded', timeout: 20000 })
      await page.waitForSelector('.navbar', { timeout: 10000 })
      await page.waitForSelector('.category-tab', { timeout: 8000 })
    } else {
      await gotoReady(page, '/product/missing-smoke-id')
      const emptyDetail = await page.$('.detail-page .empty-state, .empty-state')
      if (!emptyDetail) fail('product detail empty state missing when catalog is empty')
      ok('product detail designed empty state is present')
      await gotoReady(page, '/')
      await page.waitForSelector('.category-tab', { timeout: 8000 })
    }

    const agentTab = page.locator('.category-tab', { hasText: 'Agent' }).first()
    await agentTab.click()
    await page.waitForTimeout(500)
    const afterTabUrl = page.url()
    const agentActive = await agentTab.evaluate((el) => el.classList.contains('active'))
    console.log(`After Agent click: url=${afterTabUrl} active=${agentActive}`)
    if (!afterTabUrl.includes('category=Agent') && !agentActive) {
      fail('category tab click did not change URL or active tab')
    }
    ok('category tab click changed catalog/URL')

    const searchAgain = await page.$('.navbar-search .search-input, .search-input')
    await searchAgain.fill(SEARCH_KEYWORD)
    await page.waitForTimeout(700)
    const afterSearchUrl = page.url()
    const resultChrome = await page.locator('.result-count, .sort-bar, .home-page').first().innerText().catch(() => '')
    console.log(`After search: url=${afterSearchUrl} chrome=${resultChrome.slice(0, 120)}`)
    if (!afterSearchUrl.includes(SEARCH_KEYWORD) && !resultChrome.includes(SEARCH_KEYWORD)) {
      fail(`search keyword "${SEARCH_KEYWORD}" not in URL or results chrome`)
    }
    ok('search produced a catalog/URL change')

    await gotoReady(page, '/bounties')
    const bountyHeading = await page.locator('h1, .bounty-header').first().innerText()
    console.log(`Bounties heading: ${bountyHeading}`)
    if (!bountyHeading.includes('悬赏')) fail(`bounties page heading missing 悬赏: ${bountyHeading}`)
    const bountySurface = await page.$('.bounty-list, .bounty-card, .empty-state, .loading-skeleton')
    if (!bountySurface) fail('bounties list / empty / loading surface missing')
    ok('悬赏 heading and list/empty/loading surface exist')
    await assertFilled(page, 'bounties')
    const bountyPath = path.join(SCREENSHOT_DIR, 'ui-bounties.png')
    await page.screenshot({ path: bountyPath, fullPage: false })
    await assertPngSize(bountyPath)
    ok(`wrote ${bountyPath}`)

    await page.locator('.floating-assistant').click()
    await page.waitForSelector('.chat-panel.open, .chat-panel', { timeout: 8000 })
    await page.waitForTimeout(450)
    const chatVisible = await page.locator('.chat-panel').first().evaluate((el) => {
      const style = window.getComputedStyle(el)
      const rect = el.getBoundingClientRect()
      return style.display !== 'none' && style.visibility !== 'hidden' && rect.width > 100 && rect.height > 200 && rect.right > 0
    })
    if (!chatVisible) fail('chat panel is not visible after clicking the floating assistant')
    const chatName = await page.locator('.chat-header-name, .chat-panel').first().innerText()
    if (!chatName.includes('BS') && !chatName.includes('助手')) {
      fail(`chat panel does not identify BS assistant: ${chatName.slice(0, 80)}`)
    }
    ok('chat panel is visible')
    const chatPath = path.join(SCREENSHOT_DIR, 'ui-chat.png')
    await page.screenshot({ path: chatPath, fullPage: false })
    await assertPngSize(chatPath)
    ok(`wrote ${chatPath}`)

    if (pageErrors.length) {
      fail(`page errors from app code: ${pageErrors.join(' | ')}`)
    }
    ok('zero page errors from app code')

    console.log('UI SMOKE PASSED')
    await browser.close()
    process.exit(0)
  } catch (err) {
    console.error(err && err.stack ? err.stack : err)
    try {
      await page.screenshot({
        path: path.join(SCREENSHOT_DIR, 'ui-smoke-failure.png'),
        fullPage: false,
      })
    } catch {
      /* ignore */
    }
    await browser.close().catch(() => {})
    process.exit(1)
  }
})()
