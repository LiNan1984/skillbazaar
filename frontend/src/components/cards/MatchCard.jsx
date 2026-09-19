import { useEffect, useState } from 'react'
import { CheckCircle, Star, ShoppingCart, AlertCircle } from 'lucide-react'
import { buyProduct, getLibrary } from '../../services/api'

function openWallet() {
  // The wallet/recharge panel lives in the app shell navbar.
  document.querySelector('.wallet-display')?.click()
}

export default function MatchCard({ card, authToken, userId }) {
  const steps = card?.steps || []
  const [purchasedIds, setPurchasedIds] = useState(() => new Set())
  const [buyingId, setBuyingId] = useState(null)
  const [remaining, setRemaining] = useState(null)
  // Per-step failure message; keyed by product id.
  const [errors, setErrors] = useState({})

  useEffect(() => {
    if (!authToken || !userId) return
    let cancelled = false
    getLibrary(authToken)
      .then((data) => {
        if (cancelled) return
        const ids = (data?.data || []).map((item) => item.id)
        setPurchasedIds(new Set(ids))
      })
      .catch(() => {
        // 401/network: stay unpurchased, purchase attempts surface the error
      })
    return () => {
      cancelled = true
    }
  }, [authToken, userId])

  const markPurchased = (productId) => {
    setPurchasedIds((prev) => {
      const next = new Set(prev)
      next.add(productId)
      return next
    })
  }

  const handleBuy = async (step) => {
    const product = step.product
    if (buyingId === product.id || purchasedIds.has(product.id)) return
    if (!authToken) {
      setErrors((prev) => ({ ...prev, [product.id]: '请先登录后再购买' }))
      return
    }
    // Path: click buy -> confirm -> success receipt (<= 3 steps).
    if (!window.confirm(`确认以 ${product.price} 金币购买「${product.name}」？`)) return

    setBuyingId(product.id)
    setErrors((prev) => {
      const next = { ...prev }
      delete next[product.id]
      return next
    })
    try {
      const result = await buyProduct(product.id, authToken)
      markPurchased(product.id)
      const balance = result?.data?.remaining_balance
      if (typeof balance === 'number') setRemaining(balance)
    } catch (err) {
      const detail = err?.detail || ''
      if (detail.includes('已购买')) {
        // Server is the source of truth: sync purchased state on 400.
        markPurchased(product.id)
      } else if (detail.includes('余额不足')) {
        setErrors((prev) => ({ ...prev, [product.id]: detail }))
      } else if (detail.includes('登录') || err?.status === 401) {
        setErrors((prev) => ({ ...prev, [product.id]: '登录已过期，请重新登录' }))
      } else {
        // Network/unknown error: button stays clickable for retry.
        setErrors((prev) => ({
          ...prev,
          [product.id]: detail || '网络异常，请稍后重试',
        }))
      }
    } finally {
      setBuyingId(null)
    }
  }

  if (!steps.length) return null

  return (
    <div className="publish-card">
      <div className="publish-card-header">任务拆解 · Skill 组合推荐</div>
      <div className="publish-card-preview" style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
        {steps.map((step, index) => {
          const product = step.product
          const purchased = purchasedIds.has(product.id)
          const buying = buyingId === product.id
          const error = errors[product.id]
          const insufficient = error && error.includes('余额不足')
          return (
            <div
              key={`${product.id}-${index}`}
              style={{
                border: '1px solid var(--border-color, #e5e7eb)',
                borderRadius: 8,
                padding: 10,
                background: purchased ? 'rgba(34,197,94,0.08)' : 'transparent',
              }}
            >
              <div style={{ fontWeight: 600, marginBottom: 6 }}>
                {index + 1}. {step.title}
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between', gap: 8, alignItems: 'flex-start' }}>
                <div style={{ minWidth: 0 }}>
                  <a href={`/product/${product.id}`} style={{ fontWeight: 600 }}>
                    {product.name}
                  </a>
                  <div style={{ fontSize: 12, opacity: 0.75 }}>
                    {product.category}
                    {product.rating != null && (
                      <span style={{ marginLeft: 8 }}>
                        <Star size={12} style={{ verticalAlign: '-1px' }} /> {Number(product.rating).toFixed(1)}
                      </span>
                    )}
                  </div>
                  <div style={{ marginTop: 4, fontSize: 13 }}>
                    <span style={{ fontWeight: 600 }}>{'￥'}{product.price} 金币</span>
                  </div>
                </div>
                <button
                  className="publish-card-btn primary"
                  onClick={() => handleBuy(step)}
                  disabled={purchased || buying || !authToken}
                  style={{ flexShrink: 0, whiteSpace: 'nowrap' }}
                >
                  {purchased ? (
                    <><CheckCircle size={14} /> 已购</>
                  ) : buying ? (
                    '购买中...'
                  ) : (
                    <><ShoppingCart size={14} /> 一键购买</>
                  )}
                </button>
              </div>
              {step.reason && (
                <div style={{ marginTop: 6, fontSize: 12, opacity: 0.8 }}>
                  推荐理由：{step.reason}
                </div>
              )}
              {error && (
                <div className="publish-card-error" style={{ marginTop: 6 }}>
                  <AlertCircle size={14} style={{ verticalAlign: '-2px', marginRight: 4 }} />
                  {error}
                  {insufficient && (
                    <button
                      className="publish-card-btn secondary"
                      style={{ marginLeft: 8, padding: '2px 8px' }}
                      onClick={openWallet}
                    >
                      去充值
                    </button>
                  )}
                </div>
              )}
            </div>
          )
        })}
      </div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: 10, fontWeight: 600 }}>
        <span>组合总价</span>
        <span>{'￥'}{card.total_price} 金币</span>
      </div>
      {remaining != null && (
        <div style={{ marginTop: 6, fontSize: 12, color: '#16a34a' }}>
          购买成功，当前剩余余额 {remaining} 金币
        </div>
      )}
    </div>
  )
}
