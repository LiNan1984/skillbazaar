const QUICK_ACTIONS = [
  { emoji: '\uD83D\uDD0D', label: '搜索商品', value: '帮我搜索商品' },
  { emoji: '\uD83D\uDE80', label: '发布Skill', value: '我想发布一个Skill' },
  { emoji: '\uD83E\uDD16', label: '发布Agent', value: '我想发布一个Agent' },
  { emoji: '\u23F0', label: '上传Cron', value: '我想上传一个Cron定时任务' },
  { emoji: '\uD83D\uDCB0', label: '发悬赏', value: '我想发一个悬赏' },
  { emoji: '\uD83D\uDCCA', label: 'Skill分析', value: '帮我分析一下全体市场的Skill数据' },
]

export default function WelcomeCard({ onAction }) {
  return (
    <div className="welcome-card">
      <div className="welcome-card-grid">
        {QUICK_ACTIONS.map((action) => (
          <button
            key={action.label}
            className="welcome-card-btn"
            onClick={() => onAction?.(action.value)}
          >
            <span className="welcome-card-emoji">{action.emoji}</span>
            <span className="welcome-card-label">{action.label}</span>
          </button>
        ))}
      </div>
    </div>
  )
}
