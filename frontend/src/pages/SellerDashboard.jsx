import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { Package, TrendingUp, Eye, EyeOff, ArrowUpDown, BarChart3 } from 'lucide-react'
import { getMyProducts, getSellerStats, updateProductStatus } from '../services/api'

const CATEGORY_CONFIG = {
  Agent: { emoji: '🤖' },
  Skill: { emoji: '⚡' },
  Cron: { emoji: '⏰' },
  Workflow: { emoji: '🔄' },
}

export default function SellerDashboard({ userId, authToken }) {
  const navigate = useNavigate()
  const [products, setProducts] = useState([])
  const [stats, setStats] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    if (!authToken) return
    loadData()
  }, [authToken])

  const loadData = async () => {
    setLoading(true)
    try {
      const [productsData, statsData] = await Promise.all([
        getMyProducts(authToken),
        getSellerStats(authToken),
      ])
      setProducts(productsData.products || [])
      setStats(statsData)
    } catch (err) {
      console.error('Failed to load seller data:', err)
    } finally {
      setLoading(false)
    }
  }

  const toggleStatus = async (productId, currentStatus) => {
    const newStatus = currentStatus === 'active' ? 'inactive' : 'active'
    try {
      await updateProductStatus(productId, newStatus, '', authToken)
      setProducts(products.map(p =>
        p.id === productId ? { ...p, status: newStatus } : p
      ))
      loadData()
    } catch (err) {
      console.error('Failed to update status:', err)
    }
  }

  if (!authToken) {
    return (
      <div className="detail-page">
        <div className="empty-state">
          <span className="empty-icon">🔒</span>
          <h3>请先登录</h3>
          <p>登录后查看你的卖家中心</p>
        </div>
      </div>
    )
  }

  return (
    <div className="detail-page">
      <div className="detail-breadcrumb">
        <span className="detail-breadcrumb-current">卖家中心</span>
      </div>

      {stats && (
        <div className="seller-stats-grid">
          <div className="seller-stat-card">
            <Package size={20} />
            <div>
              <span className="stat-value">{stats.product_count}</span>
              <span className="stat-label">全部商品</span>
            </div>
          </div>
          <div className="seller-stat-card">
            <Eye size={20} />
            <div>
              <span className="stat-value">{stats.active_count}</span>
              <span className="stat-label">在售</span>
            </div>
          </div>
          <div className="seller-stat-card">
            <EyeOff size={20} />
            <div>
              <span className="stat-value">{stats.inactive_count}</span>
              <span className="stat-label">已下架</span>
            </div>
          </div>
          <div className="seller-stat-card">
            <TrendingUp size={20} />
            <div>
              <span className="stat-value">{stats.total_sales}</span>
              <span className="stat-label">总销量</span>
            </div>
          </div>
        </div>
      )}

      <div className="seller-actions">
        <button className="btn btn-primary" onClick={() => navigate('/publish')}>
          发布新商品
        </button>
      </div>

      {loading ? (
        <div className="detail-skeleton">
          <div className="skeleton-line shimmer" style={{ width: '100%', height: '60px' }} />
          <div className="skeleton-line shimmer" style={{ width: '100%', height: '60px' }} />
        </div>
      ) : products.length === 0 ? (
        <div className="empty-state">
          <span className="empty-icon">📦</span>
          <h3>暂无商品</h3>
          <p>发布你的第一个 Agent、Skill 或 Cron 开始赚钱</p>
          <button className="btn btn-primary" onClick={() => navigate('/publish')}>
            发布商品
          </button>
        </div>
      ) : (
        <div className="seller-products-list">
          <div className="seller-list-header">
            <span>商品</span>
            <span>分类</span>
            <span>价格</span>
            <span>销量</span>
            <span>状态</span>
            <span>操作</span>
          </div>
          {products.map((p) => {
            const catConfig = CATEGORY_CONFIG[p.category] || { emoji: '📦' }
            return (
              <div key={p.id} className={`seller-list-row ${p.status !== 'active' ? 'inactive' : ''}`}>
                <div className="seller-product-info" onClick={() => navigate(`/product/${p.id}`)}>
                  <span className="seller-product-emoji">{catConfig.emoji}</span>
                  <div>
                    <strong>{p.name}</strong>
                    <small>{p.description?.slice(0, 40) || ''}</small>
                  </div>
                </div>
                <span>{p.category}</span>
                <span className="seller-price">¥{p.price}</span>
                <span>{p.sales || 0}</span>
                <span className={`status-badge ${p.status}`}>
                  {p.status === 'active' ? '在售' : '已下架'}
                </span>
                <div className="seller-actions-cell">
                  <button
                    className={`btn-sm ${p.status === 'active' ? 'btn-delist' : 'btn-relist'}`}
                    onClick={() => toggleStatus(p.id, p.status)}
                  >
                    {p.status === 'active' ? '下架' : '上架'}
                  </button>
                </div>
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}
