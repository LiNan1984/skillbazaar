import { useState, useEffect, useCallback } from 'react'
import { useParams, useNavigate, Link } from 'react-router-dom'
import {
  Download,
  Star,
  ShoppingCart,
  ExternalLink,
  Tag,
  ChevronRight,
  Home,
  Box,
  Zap,
  Monitor,
  Play,
  CheckCircle2,
  XCircle,
  AlertCircle,
  Copy,
} from 'lucide-react'
import { getProduct, getProducts, getUser, getMe, getLibrary, executeSkill, downloadSkillZip, saveBlobAsFile } from '../services/api'
import PurchaseModal from '../components/PurchaseModal'
import ProductCard from '../components/ProductCard'
import ProductReviews from '../components/ProductReviews'
import { useLang } from '../i18n'

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

function parseCompat(compat) {
  if (!compat) return []
  if (Array.isArray(compat)) return compat
  try { return JSON.parse(compat) } catch { return [] }
}

function evalScoreColor(score) {
  if (score == null) return null
  if (score >= 80) return '#22c55e'
  if (score >= 60) return '#fbbf24'
  return '#f87171'
}

function evalStatusLabel(status) {
  const map = {
    passed: 'pd.evalPass',
    failed: 'pd.evalFail',
    pending: 'pd.evalPending',
    completed: 'pd.evalPass',
  }
  return map[status] || status
}

export default function ProductDetailPage({ userId, authToken }) {
  const { id } = useParams()
  const navigate = useNavigate()
  const { t, lang } = useLang()
  const [product, setProduct] = useState(null)
  const [related, setRelated] = useState([])
  const [loading, setLoading] = useState(true)
  const [balance, setBalance] = useState(0)
  const [showPurchase, setShowPurchase] = useState(false)
  const [owned, setOwned] = useState(false)
  const [downloading, setDownloading] = useState(false)

  // Trial execution state
  const [trialInput, setTrialInput] = useState('')
  const [trialRunning, setTrialRunning] = useState(false)
  const [trialResult, setTrialResult] = useState(null)
  const [trialError, setTrialError] = useState(null)
  const [evalReport, setEvalReport] = useState(null)

  const handleDownload = async () => {
    if (!owned) {
      setShowPurchase(true)
      return
    }
    setDownloading(true)
    try {
      const token = authToken || localStorage.getItem('skillbazaar_token')
      const res = await downloadSkillZip(id, { token, userId })
      saveBlobAsFile(res.data, `${product?.name || 'skill'}.zip`)
    } catch (err) {
      const msg = err?.response?.data?.detail || err?.response?.data?.error || '下载失败，请稍后重试'
      alert(typeof msg === 'string' ? msg : '下载失败，请稍后重试')
    } finally {
      setDownloading(false)
    }
  }

  useEffect(() => {
    setLoading(true)
    getProduct(id)
      .then((data) => {
        setProduct(data)
        // Extract eval report from product
        if (data.eval_report) {
          setEvalReport(data.eval_report)
        }
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
    if (userId && authToken) {
      getLibrary(authToken)
        .then((res) => {
          const items = res.data || res.items || res || []
          const isOwned = items.some(p => String(p.id) === String(id))
          setOwned(isOwned)
        })
        .catch(() => {})
    }
  }, [id, userId, authToken])

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

  const handleRated = useCallback((avgRating) => {
    setProduct((prev) => {
      if (prev && Math.abs((prev.rating ?? 0) - avgRating) > 0.01) {
        return { ...prev, rating: avgRating }
      }
      return prev
    })
  }, [])

  const handleTrialRun = async () => {
    setTrialRunning(true)
    setTrialResult(null)
    setTrialError(null)
    try {
      let inputParams = null
      if (trialInput.trim()) {
        try { inputParams = JSON.parse(trialInput) } catch {
          setTrialError('Invalid JSON input')
          setTrialRunning(false)
          return
        }
      }
      const result = await executeSkill(id, userId || 'anonymous', inputParams ? JSON.stringify(inputParams) : null)
      if (result?.error) {
        const raw = String(result.error)
        const friendly = /Bearer|API.?key|header/i.test(raw)
          ? '技能执行服务暂未配置，请稍后再试或联系卖家'
          : raw
        setTrialError(friendly)
      } else {
        setTrialResult(result)
      }
    } catch (err) {
      setTrialError(err?.detail || err?.message || 'Trial execution failed')
    } finally {
      setTrialRunning(false)
    }
  }

  const copyTrialOutput = () => {
    if (trialResult?.output) {
      navigator.clipboard?.writeText(String(trialResult.output))
    }
  }

  if (loading) {
    return (
      <div className="detail-page page-shell">
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
      <div className="detail-page page-shell">
        <div className="empty-state">
          <span className="empty-icon">😔</span>
          <h3>{t('pd.notFound')}</h3>
          <p>{t('pd.notFoundDesc')}</p>
          <button className="btn btn-primary" onClick={() => navigate('/')}>
            {t('pd.backHome')}
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

  const compatList = parseCompat(product.compat)
  const hasCompat = compatList.length > 0

  const currentEvalScore = evalReport?.eval_score ?? product.eval_score ?? null
  const currentEvalStatus = evalReport?.status ?? null

  return (
    <div className="detail-page page-shell">
      <div className="detail-breadcrumb">
        <Link to="/"><Home size={14} /> {lang === 'zh' ? '首页' : 'Home'}</Link>
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
                  {downloads} {t('pd.downloads')}
                </span>
                <span className="detail-stat">
                  <ShoppingCart size={14} />
                  {sales} {t('pd.sales')}
                </span>
              </div>
            </div>
          </div>

          {hasCompat && (
            <div className="detail-section detail-compat-section">
              <h2>{t('pd.compat')}</h2>
              <div className="detail-compat-badges">
                {compatList.map((c) => {
                  const cfg = COMPAT_CONFIG[c] || { label: c, icon: '📦', color: '#71717a' }
                  return (
                    <span key={c} className="compat-badge detail-compat-badge" style={{ '--compat-color': cfg.color }}>
                      <span className="compat-badge-icon">{cfg.icon}</span>
                      {cfg.label}
                    </span>
                  )
                })}
              </div>
            </div>
          )}

          {(() => { let pt = []; try { pt = typeof product.tags === 'string' ? JSON.parse(product.tags || '[]') : (product.tags || []); } catch { pt = []; } return pt.length > 0 && (
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
            <h2>{t('pd.description')}</h2>
            <p className="detail-description">{product.description}</p>
          </div>

          {currentEvalScore != null && (
            <div className="detail-section detail-eval-section">
              <h2>{t('pd.evalScore')}</h2>
              <div className="detail-eval-card">
                <div className="detail-eval-score-ring" style={{ '--score-color': evalScoreColor(currentEvalScore) }}>
                  <span className="detail-eval-score-value">{currentEvalScore}</span>
                  <span className="detail-eval-score-max">/100</span>
                </div>
                <div className="detail-eval-info">
                  {currentEvalStatus && (
                    <span className={`detail-eval-status detail-eval-status-${currentEvalStatus}`}>
                      {currentEvalStatus === 'passed' || currentEvalStatus === 'completed' ? <CheckCircle2 size={14} /> :
                       currentEvalStatus === 'failed' ? <XCircle size={14} /> :
                       <AlertCircle size={14} />}
                      {t(evalStatusLabel(currentEvalStatus))}
                    </span>
                  )}
                  {evalReport?.reason && (
                    <p className="detail-eval-reason">{evalReport.reason}</p>
                  )}
                  {evalReport?.static_flags && evalReport.static_flags.length > 0 && (
                    <div className="detail-eval-flags">
                      {evalReport.static_flags.map((f) => (
                        <span key={f} className="eval-flag eval-flag-static">{f}</span>
                      ))}
                    </div>
                  )}
                  {evalReport?.flags && evalReport.flags.length > 0 && (
                    <div className="detail-eval-flags">
                      {evalReport.flags.map((f) => (
                        <span key={f} className="eval-flag eval-flag-runtime">{f}</span>
                      ))}
                    </div>
                  )}
                </div>
              </div>
            </div>
          )}

          {product.content_preview && (
            <div className="detail-section">
              <h2>{t('pd.contentPreview')}</h2>
              <div className="code-preview">
                <pre>
                  <code>{product.content_preview}</code>
                </pre>
              </div>
            </div>
          )}

          <div className="detail-section">
            <a
              href={`/api/discovery/products/${product.id}/skill.md`}
              target="_blank"
              rel="noopener noreferrer"
              className="github-link"
            >
              <ExternalLink size={16} />
              {lang === 'zh' ? '导出 SKILL.md' : 'Export SKILL.md'}
            </a>
          </div>

          {product.github_url && (
            <div className="detail-section">
              <a
                href={product.github_url}
                target="_blank"
                rel="noopener noreferrer"
                className="github-link"
              >
                <ExternalLink size={16} />
                {lang === 'zh' ? '查看 GitHub 仓库' : 'View GitHub Repo'}
              </a>
            </div>
          )}

          {/* Trial Execution */}
          <div className="detail-section skill-execute-section">
            <h2>{t('pd.trialTitle')}</h2>
            <p className="skill-execute-desc">{t('pd.trialDesc')}</p>
            <div className="trial-input-row">
              <textarea
                className="skill-execute-input trial-input"
                placeholder={t('pd.trialInput')}
                value={trialInput}
                onChange={(e) => setTrialInput(e.target.value)}
                rows={3}
              />
              <button
                className="btn btn-primary skill-sandbox-btn trial-run-btn"
                onClick={handleTrialRun}
                disabled={trialRunning}
              >
                {trialRunning ? (
                  <>{t('common.loading')}</>
                ) : (
                  <><Play size={16} /> {t('pd.trialRun')}</>
                )}
              </button>
            </div>
            {!authToken && (
              <p className="trial-auth-hint">{t('pd.trialNoAuth')}</p>
            )}
            {trialResult && (
              <div className="skill-execute-output">
                <h4>{t('pd.trialOutput')}</h4>
                <div className="trial-output-header">
                  <span className="trial-output-status trial-success">
                    <CheckCircle2 size={14} />
                    {t('pd.trialSuccess')}
                  </span>
                  <button className="trial-copy-btn" onClick={copyTrialOutput} title="Copy">
                    <Copy size={14} />
                  </button>
                </div>
                <pre><code>{JSON.stringify(trialResult, null, 2)}</code></pre>
              </div>
            )}
            {trialError && (
              <div className="trial-error">
                <XCircle size={14} />
                {trialError}
              </div>
            )}
          </div>

          <div className="detail-section skill-execute-section">
            <h2>{t('pd.trySkill')}</h2>
            <p className="skill-execute-desc">{t('pd.trySkillDesc')}</p>
            <div className="skill-sandbox-cta">
              {owned ? (
                <button
                  className="btn btn-primary skill-sandbox-btn"
                  onClick={() => navigate(`/sandbox?tab=chat&agent=${encodeURIComponent(product.name)}&msg=${encodeURIComponent(lang === 'zh' ? '请帮我使用这个技能' : 'Help me use this skill')}`)}
                >
                  <Box size={18} />
                  {t('pd.ownedUse')}
                </button>
              ) : (
                <div className="skill-sandbox-locked">
                  <p className="skill-sandbox-locked-text">{t('pd.notOwned')}</p>
                  <button
                    className="btn btn-primary skill-sandbox-btn"
                    onClick={() => setShowPurchase(true)}
                  >
                    <ShoppingCart size={16} />
                    {t('pd.buyNow')} · {'￥'}{product.price}
                  </button>
                </div>
              )}
            </div>
          </div>

          <ProductReviews
            productId={id}
            owned={owned}
            authToken={authToken}
            userId={userId}
            onRatingChange={handleRated}
          />
        </div>

        {/* Buy Panel */}
        <div className="detail-buy-panel">
          <div className="buy-panel-price">
            <span className="buy-panel-price-value">{'￥'}{product.price}</span>
            <span className="buy-panel-price-unit">{t('pd.coins')}</span>
            {product.original_price && product.original_price > product.price && (
              <span className="buy-panel-price-original">{'￥'}{product.original_price}</span>
            )}
          </div>

          <div className="buy-panel-stats">
            <span className="buy-panel-stat">
              <Star size={14} style={{ color: '#eab308' }} />
              {Number(rating).toFixed(1)} {t('pd.rating')}
            </span>
            <span className="buy-panel-stat">
              <Download size={14} />
              {downloads} {t('pd.downloads')}
            </span>
            {currentEvalScore != null && (
              <span className="buy-panel-stat" style={{ color: evalScoreColor(currentEvalScore) }}>
                <Zap size={14} />
                {t('pd.evalScore')}: {currentEvalScore}
              </span>
            )}
          </div>

          <div className="buy-panel-divider" />

          <div className="buy-panel-balance">
            <span className="buy-panel-balance-label">{t('pd.balance')}</span>
            <span className={`buy-panel-balance-value ${insufficient ? 'insufficient' : 'sufficient'}`}>
              {'￥'}{balance.toLocaleString()} {t('pd.coins')}
            </span>
          </div>

          {owned ? (
            <button className="btn-owned" onClick={() => navigate(`/sandbox?tab=chat&agent=${encodeURIComponent(product.name)}`)}>
              {t('pd.ownedUse')}
            </button>
          ) : (
            <button className="btn-buy" onClick={() => setShowPurchase(true)}>
              {t('pd.buyNow')} · {'￥'}{product.price} {t('pd.coins')}
            </button>
          )}

          <button
            className={owned ? 'btn-download-zip btn-owned-zip' : 'btn-download-zip'}
            onClick={handleDownload}
            disabled={downloading}
            title={owned ? t('pd.downloadZip') : t('pd.downloadNeedBuy')}
          >
            <Download size={16} />
            {downloading ? (lang === 'zh' ? '打包中…' : 'Packaging…') : t('pd.downloadZip')}
          </button>
        </div>

        {related.length > 0 && (
          <div className="related-section">
            <h2>{t('pd.related')}</h2>
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
          authToken={authToken}
          balance={balance}
          onClose={() => setShowPurchase(false)}
          onSuccess={() => navigate('/library')}
        />
      )}
    </div>
  )
}
