import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { Package, Calendar, Coins, CheckCircle } from 'lucide-react'
import { getLibrary } from '../services/api'

export default function MyLibraryPage({ userId }) {
  const navigate = useNavigate()
  const [items, setItems] = useState([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    if (userId) {
      setLoading(true)
      getLibrary(userId)
        .then((data) => {
          const list = data.items || data.library || data.data || []
          setItems(list)
        })
        .catch(() => setItems([]))
        .finally(() => setLoading(false))
    }
  }, [userId])

  if (loading) {
    return (
      <div className="library-page">
        <h1 className="page-title">
          <Package size={28} />
          我的库
        </h1>
        <div className="library-grid">
          {Array.from({ length: 4 }).map((_, i) => (
            <div key={i} className="library-card skeleton">
              <div className="skeleton-line shimmer" style={{ width: '60%' }} />
              <div className="skeleton-line shimmer" style={{ width: '80%' }} />
              <div className="skeleton-line shimmer" style={{ width: '40%' }} />
            </div>
          ))}
        </div>
      </div>
    )
  }

  return (
    <div className="library-page">
      <h1 className="page-title">
        <Package size={28} />
        我的库
      </h1>

      {items.length === 0 ? (
        <div className="empty-state">
          <span className="empty-icon">📦</span>
          <h3>还没有购买任何商品</h3>
          <p>去逛逛吧，发现优质的 AI 工具</p>
          <button className="btn btn-primary" onClick={() => navigate('/')}>
            浏览市场
          </button>
        </div>
      ) : (
        <div className="library-grid">
          {items.map((item) => {
            const catConfig = {
              Agent: { emoji: '🤖', css: 'cat-agent' },
              Skill: { emoji: '⚡', css: 'cat-skill' },
              Cron: { emoji: '⏰', css: 'cat-cron' },
              Workflow: { emoji: '🔄', css: 'cat-workflow' },
            }
            const cat = catConfig[item.category] || { emoji: '📦', css: 'cat-default' }

            return (
              <div
                key={item.id || item.product_id}
                className="library-card"
                onClick={() => navigate(`/product/${item.product_id || item.id}`)}
              >
                <div className="library-card-badge">
                  <CheckCircle size={10} />
                  已购买
                </div>
                <div className="library-card-header">
                  <div className={`library-card-icon product-icon-wrapper ${cat.css}`}>
                    {cat.emoji}
                  </div>
                  <h3>{item.name || item.product_name}</h3>
                </div>
                {item.description && (
                  <p className="library-card-desc">{item.description}</p>
                )}
                <div className="library-card-meta">
                  <span>
                    <Calendar size={13} />
                    {item.purchased_at
                      ? new Date(item.purchased_at).toLocaleDateString('zh-CN')
                      : '未知日期'}
                  </span>
                  <span>
                    <Coins size={13} />
                    {item.price_paid ?? item.price ?? '-'} 金币
                  </span>
                </div>
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}
