import { useState, useEffect } from 'react'
import { useParams, useNavigate, Link } from 'react-router-dom'
import {
  Download,
  Star,
  ShoppingCart,
  ExternalLink,
  Tag,
  ChevronRight,
  Home,
} from 'lucide-react'
import { getProduct, getProducts, getUser, getMe, executeSkill, getLibrary } from '../services/api'
import PurchaseModal from '../components/PurchaseModal'
import ProductCard from '../components/ProductCard'

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

export default function ProductDetailPage({ userId }) {
  const { id } = useParams()
  const navigate = useNavigate()
  const [product, setProduct] = useState(null)
  const [related, setRelated] = useState([])
  const [loading, setLoading] = useState(true)
  const [balance, setBalance] = useState(0)
  const [showPurchase, setShowPurchase] = useState(false)
  const [skillInput, setSkillInput] = useState('')
  const [skillOutput, setSkillOutput] = useState('')
  const [executing, setExecuting] = useState(false)
  const [owned, setOwned] = useState(false)

  useEffect(() => {
    setLoading(true)
    getProduct(id)
      .then((data) => {
        setProduct(data)
        if (data.category) {
          getProducts({ category: data.category, pageSize: 5 })
            .then((res) => {
              const items = res.items || res.products || res.data || []
              setRelated(items.filter((p) => String(p.id) !== String(id)).slice(0, 4))
            })
            .catch(() => {})
        }
      })
      .catch(() => setProduct(null))
      .finally(() => setLoading(false))

    // Check if user already owns this product
    if (userId) {
      getLibrary(userId)
        .then((res) => {
          const items = res.data || res.items || res || []
          const isOwned = items.some(p => String(p.id) === String(id))
          setOwned(isOwned)
        })
        .catch(() => {})
    }
  }, [id, userId])

  useEffect(() => {
    const token = localStorage.getItem('skillbazaar_token')
    if (token) {
      getMe(token)
        .then((data) => setBalance(data.coins ?? 0))
        .catch(() => {})
    } else if (userId) {
      getUser(userId)
        .then((data) => setBalance(data.balance ?? data.coins ?? 0))
        .catch(() => {})
    }
  }, [userId])

  if (loading) {
    return (
      <div className="detail-page">
        <div className="detail-skeleton">
          <div className="skeleton-line shimmer" style={{ width: '40%', height: '32px' }} />
          <div className="skeleton-line shimmer" style={{ width: '60%' }} />
          <div className="skeleton-line shimmer" style={{ width: '80%' }} />
          <div className="skeleton-line shimmer" style={{ width: '90%', height: '200px' }} />
        </div>
      </div>
    )
  }

  if (!product) {
    return (
      <div className="detail-page">
        <div className="empty-state">
          <span className="empty-icon">😔</span>
          <h3>商品不存在</h3>
          <p>该商品可能已下架</p>
          <button className="btn btn-primary" onClick={() => navigate('/')}>
            返回首页
          </button>
        </div>
      </div>
    )
  }

  const sourceColor = SOURCE_COLORS[product.source] || '#71717a'
  const catConfig = CATEGORY_CONFIG[product.category] || { emoji: '📦', cssClass: 'cat-default' }
  const rating = product.rating ?? product.avg_rating ?? 0
  const downloads = product.downloads ?? product.download_count ?? 0
  const sales = product.sales ?? product.sales_count ?? 0
  const insufficient = balance < product.price

  return (
    <div className="detail-page">
      <div className="detail-breadcrumb">
        <Link to="/"><Home size={14} /> 首页</Link>
        <ChevronRight size={14} className="detail-breadcrumb-separator" />
        <Link to={`/?category=${product.category}`}>{product.category}</Link>
        <ChevronRight size={14} className="detail-breadcrumb-separator" />
        <span className="detail-breadcrumb-current">{product.name}</span>
      </div>

      <div className="detail-layout">
        <div className="detail-main">
          <div className="detail-header">
            <div className={`detail-icon product-icon-wrapper ${catConfig.cssClass}`}>
              {catConfig.emoji}
            </div>
            <div className="detail-title-area">
              <div className="detail-title-row">
                <h1>{product.name}</h1>
                {product.source && (
                  <span className="source-badge" style={{ backgroundColor: sourceColor }}>
                    {product.source}
                  </span>
                )}
              </div>
              <div className="detail-meta">
                <span className="detail-category">{product.category}</span>
                {product.subcategory && (
                  <span className="detail-subcategory">· {product.subcategory}</span>
                )}
                <span className="detail-stat">
                  <Star size={14} style={{ color: '#eab308' }} />
                  {Number(rating).toFixed(1)}
                </span>
                <span className="detail-stat">
                  <Download size={14} />
                  {downloads} 次下载
                </span>
                <span className="detail-stat">
                  <ShoppingCart size={14} />
                  {sales} 次销售
                </span>
              </div>
            </div>
          </div>

          {(() => { const pt = typeof product.tags === 'string' ? JSON.parse(product.tags || '[]') : (product.tags || []); return pt.length > 0 && (
            <div className="detail-tags">
              <Tag size={16} />
              {pt.map((tag) => (
                <span key={tag} className="tag-pill">
                  {tag}
                </span>
              ))}
            </div>
          ) })()}

          <div className="detail-section">
            <h2>商品描述</h2>
            <p className="detail-description">{product.description}</p>
          </div>

          {product.content_preview && (
            <div className="detail-section">
              <h2>内容预览</h2>
              <div className="code-preview">
                <pre>
                  <code>{product.content_preview}</code>
                </pre>
              </div>
            </div>
          )}

          {product.github_url && (
            <div className="detail-section">
              <a
                href={product.github_url}
                target="_blank"
                rel="noopener noreferrer"
                className="github-link"
              >
                <ExternalLink size={16} />
                查看 GitHub 仓库
              </a>
            </div>
          )}

          <div className="detail-section skill-execute-section">
            <h2>体验技能</h2>
            <p className="skill-execute-desc">输入参数，体验这个技能的效果（免费试用 3 次）</p>
            <textarea
              className="form-textarea skill-execute-input"
              placeholder="输入体验参数，如：分析 BTC 行情趋势"
              value={skillInput}
              onChange={(e) => setSkillInput(e.target.value)}
              rows={3}
            />
            <button
              className="btn btn-primary skill-execute-btn"
              disabled={executing || !skillInput.trim()}
              onClick={async () => {
                setExecuting(true)
                setSkillOutput('')
                try {
                  const result = await executeSkill(product.id, userId, skillInput.trim())
                  setSkillOutput(result.output || result.error || '执行完成')
                } catch (err) {
                  setSkillOutput('执行失败：' + (err?.message || '请先购买或网络异常'))
                } finally {
                  setExecuting(false)
                }
              }}
            >
              {executing ? '执行中...' : '运行技能'}
            </button>
            {skillOutput && (
              <div className="skill-execute-output">
                <h4>输出结果</h4>
                <pre>{skillOutput}</pre>
              </div>
            )}
          </div>
        </div>

        {/* Buy Panel */}
        <div className="detail-buy-panel">
          <div className="buy-panel-price">
            <span className="buy-panel-price-value">{'\uFFE5'}{product.price}</span>
            <span className="buy-panel-price-unit">金币</span>
            {product.original_price && product.original_price > product.price && (
              <span className="buy-panel-price-original">{'\uFFE5'}{product.original_price}</span>
            )}
          </div>

          <div className="buy-panel-stats">
            <span className="buy-panel-stat">
              <Star size={14} style={{ color: '#eab308' }} />
              {Number(rating).toFixed(1)} 评分
            </span>
            <span className="buy-panel-stat">
              <Download size={14} />
              {downloads} 下载
            </span>
          </div>

          <div className="buy-panel-divider" />

          <div className="buy-panel-balance">
            <span className="buy-panel-balance-label">账户余额</span>
            <span className={`buy-panel-balance-value ${insufficient ? 'insufficient' : 'sufficient'}`}>
              {'\uFFE5'}{balance.toLocaleString()} 金币
            </span>
          </div>

          {owned ? (
            <button className="btn-owned" disabled>
              已购买 · 在我的库中
            </button>
          ) : (
            <button className="btn-buy" onClick={() => setShowPurchase(true)}>
              立即购买 · {'\uFFE5'}{product.price} 金币
            </button>
          )}
        </div>

        {related.length > 0 && (
          <div className="related-section">
            <h2>相关推荐</h2>
            <div className="product-grid related-grid">
              {related.map((p) => (
                <ProductCard key={p.id} product={p} />
              ))}
            </div>
          </div>
        )}
      </div>

      {showPurchase && (
        <PurchaseModal
          product={product}
          userId={userId}
          balance={balance}
          onClose={() => setShowPurchase(false)}
          onSuccess={() => navigate('/library')}
        />
      )}
    </div>
  )
}
