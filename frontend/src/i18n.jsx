/**
 * SkillBazaar i18n — 中英文切换系统
 * 用法: import { useLang } from '../i18n'; const { t, lang, setLang } = useLang();
 */
import { createContext, useContext, useState, useCallback } from 'react'

const ZH = 'zh'
const EN = 'en'

const translations = {
  // === Navbar ===
  'nav.search': { zh: '搜索 Agent、Skill、Cron...', en: 'Search Agents, Skills, Cron...' },
  'nav.publish': { zh: '发布商品', en: 'Publish' },
  'nav.bounties': { zh: '悬赏市场', en: 'Bounties' },
  'nav.activities': { zh: '活动中心', en: 'Activities' },
  'nav.sandbox': { zh: '沙盒', en: 'Sandbox' },
  'nav.seller': { zh: '卖家中心', en: 'Seller' },
  'nav.admin': { zh: '管理后台', en: 'Admin' },
  'nav.library': { zh: '我的库', en: 'Library' },
  'nav.login': { zh: '登录', en: 'Login' },
  'nav.register': { zh: '注册', en: 'Register' },
  'nav.wallet': { zh: '钱包', en: 'Wallet' },
  'nav.logout': { zh: '退出', en: 'Logout' },
  'nav.user': { zh: '用户', en: 'User' },

  // === SandboxPage ===
  'sb.title': { zh: '🦐 沙盒 & 开发者中心', en: '🦐 Sandbox & Dev Center' },
  'sb.subtitle': { zh: '一用户一沙盒 · 积分换时长 · 虾塘加密保护源码', en: 'One Sandbox Per User · Points for Time · Shrimp Pond Encryption' },
  'sb.loginPrompt': { zh: '登录后使用', en: 'Login to Use' },
  'sb.loginDesc': { zh: '一用户一沙盒 · 积分换时长 · 虾塘加密保护源码', en: 'One Sandbox Per User · Points for Time · Shrimp Pond Encryption' },
  'sb.remain': { zh: '剩余', en: 'Remain' },
  'sb.minutes': { zh: '分钟', en: 'min' },
  'sb.points': { zh: '积分', en: 'Points' },
  'sb.status': { zh: '状态', en: 'Status' },
  'sb.running': { zh: '运行中', en: 'Running' },
  'sb.stopped': { zh: '未启动', en: 'Stopped' },
  'sb.start': { zh: '启动沙盒', en: 'Start Sandbox' },
  'sb.stop': { zh: '停止沙盒', en: 'Stop Sandbox' },
  'sb.hours': { zh: '小时', en: 'hours' },
  'sb.redeem': { zh: '积分兑换', en: 'Redeem' },
  'sb.redeemHint': { zh: '100积分/小时', en: '100 pts/hour' },
  'sb.tab.sandbox': { zh: '沙盒执行', en: 'Execute' },
  'sb.tab.encrypt': { zh: '虾塘加密', en: 'Encrypt' },
  'sb.tab.chat': { zh: 'AI对话', en: 'AI Chat' },
  'sb.tab.developer': { zh: '开发者', en: 'Developer' },

  // Sandbox Execute Tab
  'sb.editor': { zh: '代码编辑器', en: 'Code Editor' },
  'sb.runCode': { zh: '运行代码', en: 'Run Code' },
  'sb.executing': { zh: '执行中', en: 'Executing...' },
  'sb.startFirst': { zh: '请先启动沙盒', en: 'Start sandbox first' },
  'sb.output': { zh: '📋 执行结果', en: '📋 Output' },
  'sb.clickRun': { zh: '// 点击"运行代码"查看结果...', en: '// Click "Run Code" to see results...' },
  'sb.notRunning': { zh: '// 沙盒未启动', en: '// Sandbox not started' },

  // Encrypt Tab
  'sb.encrypt.info': { zh: '虾塘加密：Agent源码加密存储 + 沙盒隔离执行，能力可售卖，源码不泄露', en: 'Shrimp Pond Encryption: Encrypted storage + sandbox execution, sell capabilities without leaking source' },
  'sb.agentSource': { zh: '📝 Agent源码', en: '📝 Agent Source' },
  'sb.agentName': { zh: 'Agent名称', en: 'Agent Name' },
  'sb.enterSource': { zh: '输入Agent源码...', en: 'Enter agent source code...' },
  'sb.encrypt': { zh: '加密', en: 'Encrypt' },
  'sb.encryptedResult': { zh: '🔐 加密结果', en: '🔐 Encrypted Result' },
  'sb.blobPlaceholder': { zh: '加密后的blob将显示在这里...', en: 'Encrypted blob will appear here...' },
  'sb.decryptVerify': { zh: '解密验证', en: 'Decrypt & Verify' },

  // Chat Tab
  'sb.chat.startFirst': { zh: '请先启动沙盒，再与NPC Agent对话', en: 'Start sandbox first to chat with NPC Agent' },
  'sb.chat.ready': { zh: 'NPC常驻Agent已就绪，直接对话吧！', en: 'NPC Agent is ready, start chatting!' },
  'sb.chat.hint': { zh: '支持多轮对话 · Agent保留上下文 · 代码执行', en: 'Multi-turn chat · Context preserved · Code execution' },
  'sb.chat.placeholder': { zh: '输入消息，按Enter发送...', en: 'Type a message, press Enter to send...' },
  'sb.chat.thinking': { zh: '思考中...', en: 'Thinking...' },

  // Developer Tab
  'sb.dev.info': { zh: 'OpenAI兼容API — 外部程序可直接调用你的Agent', en: 'OpenAI-compatible API — External programs can call your Agent directly' },
  'sb.dev.endpoint': { zh: '📡 API端点', en: '📡 API Endpoints' },
  'sb.dev.example': { zh: '💻 cURL示例', en: '💻 cURL Examples' },
  'sb.dev.openaiChat': { zh: 'OpenAI兼容对话', en: 'OpenAI-compatible Chat' },
  'sb.dev.execute': { zh: '执行代码', en: 'Execute Code' },
  'sb.dev.status': { zh: '沙盒状态', en: 'Sandbox Status' },
  'sb.dev.encryptAgent': { zh: '加密Agent', en: 'Encrypt Agent' },
  'sb.dev.decryptAgent': { zh: '解密Agent', en: 'Decrypt Agent' },

  // Product Detail Page — Skill Execute
  'pd.trySkill': { zh: '体验技能', en: 'Try Skill' },
  'pd.trySkillDesc': { zh: '购买后，在沙盒中与NPC Agent对话来使用这个技能', en: 'After purchase, use this skill by chatting with NPC Agent in sandbox' },
  'pd.goSandbox': { zh: '🦐 去沙盒使用', en: '🦐 Use in Sandbox' },
  'pd.buyFirst': { zh: '请先购买', en: 'Purchase First' },
  'pd.ownedUse': { zh: '已拥有 · 去沙盒使用', en: 'Owned · Use in Sandbox' },
  'pd.notOwned': { zh: '购买后可用', en: 'Available after purchase' },
  'pd.description': { zh: '商品描述', en: 'Description' },
  'pd.contentPreview': { zh: '内容预览', en: 'Content Preview' },
  'pd.downloadZip': { zh: '⬇️ 下载 Skill 包（zip）', en: '⬇️ Download Skill (.zip)' },
  'pd.downloadZipOk': { zh: '已开始下载', en: 'Download started' },
  'pd.downloadNeedBuy': { zh: '购买后可下载 Skill 包', en: 'Purchase to download' },
  'pd.github': { zh: '查看 GitHub 仓库', en: 'View GitHub Repo' },
  'pd.notFound': { zh: '商品不存在', en: 'Product Not Found' },
  'pd.notFoundDesc': { zh: '该商品可能已下架', en: 'This product may have been delisted' },
  'pd.backHome': { zh: '返回首页', en: 'Back to Home' },
  'pd.buyNow': { zh: '立即购买', en: 'Buy Now' },
  'pd.owned': { zh: '已购买 · 在我的库中', en: 'Purchased · In Library' },
  'pd.coins': { zh: '金币', en: 'coins' },
  'pd.balance': { zh: '账户余额', en: 'Balance' },
  'pd.related': { zh: '相关推荐', en: 'Related' },
  'pd.output': { zh: '输出结果', en: 'Output' },
  'pd.downloads': { zh: '次下载', en: 'downloads' },
  'pd.sales': { zh: '次销售', en: 'sales' },
  'pd.rating': { zh: '评分', en: 'rating' },
  'pd.evalScore': { zh: '评测得分', en: 'Eval Score' },
  'pd.evalPending': { zh: '评测中', en: 'Evaluating' },
  'pd.evalPass': { zh: '通过', en: 'Pass' },
  'pd.evalFail': { zh: '未通过', en: 'Fail' },
  'pd.compat': { zh: '运行环境', en: 'Compatibility' },
  'pd.trialTitle': { zh: '试用运行', en: 'Trial Run' },
  'pd.trialDesc': { zh: '免费试用一次（匿名用户每个IP限1次/小时）', en: 'Free trial (anonymous users: 1/hr per IP)' },
  'pd.trialInput': { zh: '输入参数（JSON，可选）', en: 'Input params (JSON, optional)' },
  'pd.trialRun': { zh: '🚀 免费试用', en: '🚀 Trial Run' },
  'pd.trialOutput': { zh: '试用输出', en: 'Trial Output' },
  'pd.trialSuccess': { zh: '试用成功！', en: 'Trial succeeded!' },
  'pd.trialNoAuth': { zh: '登录后可查看更多试用次数', en: 'Login for more trial credits' },
  'pd.compatClaude': { zh: 'Claude Code', en: 'Claude Code' },
  'pd.compatCodex': { zh: 'Codex CLI', en: 'Codex CLI' },
  'pd.compatPrompt': { zh: '纯提示词', en: 'Prompt Only' },
  'pd.compatSdk': { zh: 'SDK', en: 'SDK' },

  // Common
  'common.loading': { zh: '加载中...', en: 'Loading...' },
  'common.error': { zh: '出错了', en: 'Error' },
  'common.success': { zh: '成功', en: 'Success' },
  'common.cancel': { zh: '取消', en: 'Cancel' },
  'common.confirm': { zh: '确认', en: 'Confirm' },
}

const LangContext = createContext({
  lang: ZH,
  setLang: () => {},
  t: (key) => key,
})

export function LangProvider({ children }) {
  const [lang, setLangState] = useState(() => localStorage.getItem('skbz_lang') || ZH)

  const setLang = useCallback((newLang) => {
    setLangState(newLang)
    localStorage.setItem('skbz_lang', newLang)
  }, [])

  const t = useCallback((key) => {
    const entry = translations[key]
    if (!entry) return key
    return entry[lang] || entry[ZH] || key
  }, [lang])

  return (
    <LangContext.Provider value={{ lang, setLang, t }}>
      {children}
    </LangContext.Provider>
  )
}

export function useLang() {
  return useContext(LangContext)
}

export { ZH, EN }
