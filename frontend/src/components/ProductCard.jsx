import { useNavigate } from 'react-router-dom'
import { Download, Star, Zap, Monitor } from 'lucide-react'

const SOURCE_COLORS = {
  Gate: '#3b82f6',
  BitMart: '#f97316',
  AgentSkillsHub: '#22c55e',
  Agensi: '#ec4899',
  社区: '#71717a',
}

const CATEGORY_CONFIG = {
  Agent: { emoji: '🤖', cssClass: 'cat-agent' },
  Skill: { emoji: '⚡', cssClass: 'cat-skill' },
  Cron: { emoji: '⏰', cssClass: 'cat-cron' },
  Workflow: { emoji: '🔄', cssClass: 'cat-workflow' },
}

const COMPAT_CONFIG = {
  'claude-code': { label: 'Claude', icon: '🟣', color: '#a78bfa' },
  'codex': { label: 'Codex', icon: '🔵', color: '#60a5fa' },
  'prompt': { label: 'Prompt', icon: '⚡', color: '#fbbf24' },
  'sdk': { label: 'SDK', icon: '🔧', color: '#34d399' },
}

function evalScoreColor(score) {
  if (score == null) return null
  if (score >= 80) return '#22c55e'
  if (score >= 60) return '#fbbf24'
  return '#f87171'
}

function parseCompat(compat) {
  if (!compat) return []
  if (Array.isArray(compat)) return compat
  try { return JSON.parse(compat) } catch { return [] }
}

export default function ProductCard({ product }) {
  const navigate = useNavigate()

  const handleCardClick = () => {
    navigate(`/product/${product.id}`)
  }

  const sourceColor = SOURCE_COLORS[product.source] || '#71717a'
  const catConfig = CATEGORY_CONFIG[product.category] || { emoji: '📦', cssClass: 'cat-default' }
  const rawTags = typeof product.tags === 'string' ? JSON.parse(product.tags || '[]') : (product.tags || [])
  const tags = rawTags.slice(0, 3)
  const rating = product.rating ?? product.avg_rating ?? 0
  const downloads = product.downloads ?? product.download_count ?? 0

  const compatList = parseCompat(product.compat)
  const evalReport = product.eval_report
  const evalScore = evalReport?.eval_score ?? evalReport?.score ?? null

  const showCompat = compatList.length > 0
  const showEval = evalScore != null

  return (
    <div className="product-card" onClick={handleCardClick}>
      <div className="product-card-top">
        <div className={`product-icon-wrapper ${catConfig.cssClass}`}>
          {catConfig.emoji}
        </div>
        {product.source && (
          <span className="source-badge" style={{ backgroundColor: sourceColor }}>
            {product.source}
          </span>
        )}
      </div>

      <h3 className="product-name">{product.name}</h3>

      <p className="product-description">{product.description}</p>

      {showCompat && (
        <div className="product-compat">
          {compatList.map((c) => {
            const cfg = COMPAT_CONFIG[c] || { label: c, icon: '📦', color: '#71717a' }
            return (
              <span key={c} className="compat-badge" style={{ '--compat-color': cfg.color }}>
                <span className="compat-badge-icon">{cfg.icon}</span>
                {cfg.label}
              </span>
            )
          })}
        </div>
      )}

      {tags.length > 0 && (
        <div className="product-tags">
          {tags.map((tag) => (
            <span key={tag} className="tag-pill">
              {tag}
            </span>
          ))}
        </div>
      )}

      <div className="product-card-stats">
        <span className="product-rating">
          <Star size={13} />
          {Number(rating).toFixed(1)}
        </span>
        <span className="product-downloads">
          <Download size={13} />
          {downloads >= 1000 ? `${(downloads / 1000).toFixed(1)}k` : downloads}
        </span>
        {showEval && (
          <span className="product-eval" style={{ color: evalScoreColor(evalScore) }}>
            <Zap size={13} />
            {evalScore}
          </span>
        )}
      </div>

      <div className="product-card-footer">
        <div className="product-price-row">
          <span className="product-price">{'￥'}{product.price}</span>
          <span className="product-price-currency">金币</span>
          {product.original_price && product.original_price > product.price && (
            <span className="product-original-price">{'￥'}{product.original_price}</span>
          )}
        </div>
        <div className="product-seller">
          <div className="product-seller-avatar">👤</div>
          <span>{product.seller_name || '匿名卖家'}</span>
        </div>
      </div>
    </div>
  )
}
