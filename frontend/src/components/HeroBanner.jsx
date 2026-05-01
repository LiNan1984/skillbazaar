import { useNavigate } from 'react-router-dom'

const ADVANTAGES = [
  {
    icon: '🔒',
    title: '加密保护',
    desc: 'AES-256-GCM 加密存储，License 授权机制，防止二次转卖',
    tag: '独家',
  },
  {
    icon: '⚡',
    title: '托管执行',
    desc: '一键在线运行，无需本地部署，沙箱隔离安全可靠',
    tag: '核心',
  },
  {
    icon: '📊',
    title: '动态定价',
    desc: '市场价格机制，基于需求、质量、时间自动调整价格',
    tag: '智能',
  },
  {
    icon: '🎯',
    title: '悬赏定制',
    desc: '发布需求，开发者竞标接单，定制专属技能',
    tag: '灵活',
  },
]

export default function HeroBanner() {
  const navigate = useNavigate()

  return (
    <section className="hero-banner">
      <div className="hero-content">
        <div className="hero-badge">
          <span className="hero-badge-dot" />
          技能加密 · 托管执行 · 悬赏定制
        </div>

        <h1 className="hero-title">
          <span className="hero-title-gradient">AI Skill</span> 智能交易市场
        </h1>

        <p className="hero-subtitle">
          发现、购买和发布 AI Agent / Skill / Cron / Workflow，<br />
          加密保护 + 托管执行 + 动态定价 + 悬赏定制
        </p>

        <div className="hero-actions">
          <button className="btn btn-primary" onClick={() => navigate('/')}>
            探索市场
          </button>
          <button className="btn btn-ghost" onClick={() => navigate('/bounties')}>
            悬赏市场
          </button>
          <button className="btn btn-ghost" onClick={() => navigate('/publish')}>
            发布商品
          </button>
        </div>

        <div className="hero-stats">
          <div className="hero-stat">
            <span className="hero-stat-value">97+</span>
            <span className="hero-stat-label">优质技能</span>
          </div>
          <div className="hero-stat-divider" />
          <div className="hero-stat">
            <span className="hero-stat-value">4</span>
            <span className="hero-stat-label">技能类型</span>
          </div>
          <div className="hero-stat-divider" />
          <div className="hero-stat">
            <span className="hero-stat-value">10K</span>
            <span className="hero-stat-label">注册即送</span>
          </div>
        </div>
      </div>

      <div className="hero-advantages">
        <h2 className="hero-advantages-title">为什么选择 SkillBazaar？</h2>
        <div className="hero-advantages-grid">
          {ADVANTAGES.map((adv) => (
            <div key={adv.title} className="hero-advantage-card">
              <div className="hero-advantage-icon">{adv.icon}</div>
              <div className="hero-advantage-content">
                <div className="hero-advantage-header">
                  <h3>{adv.title}</h3>
                  <span className="hero-advantage-tag">{adv.tag}</span>
                </div>
                <p>{adv.desc}</p>
              </div>
            </div>
          ))}
        </div>
        <div className="hero-comparison">
          <div className="hero-comparison-item">
            <span className="hero-comparison-label">GitHub 免费 SKILL.md</span>
            <span className="hero-comparison-minus">明文公开 · 无执行 · 无保护 · 无变现</span>
          </div>
          <div className="hero-comparison-vs">VS</div>
          <div className="hero-comparison-item highlight">
            <span className="hero-comparison-label">SkillBazaar 付费技能</span>
            <span className="hero-comparison-plus">加密保护 · 托管运行 · 动态定价 · 悬赏交易</span>
          </div>
        </div>
      </div>
    </section>
  )
}
