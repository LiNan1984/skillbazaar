import { useState, useEffect } from 'react'
import { useParams, useNavigate, Link } from 'react-router-dom'
import { Home, ChevronRight, Clock, DollarSign, Users, Send, CheckCircle, XCircle, Trash2 } from 'lucide-react'
import { getBounty, applyForBounty, selectBountyDeveloper, deliverBounty, reviewBountyDelivery, deleteBounty } from '../services/api'

const STATUS_MAP = {
  open: { label: '招募中', color: '#22c55e' },
  in_progress: { label: '开发中', color: '#3b82f6' },
  delivered: { label: '已交付', color: '#f59e0b' },
  completed: { label: '已完成', color: '#6366f1' },
  cancelled: { label: '已取消', color: '#ef4444' },
}

export default function BountyDetailPage({ userId, authToken }) {
  const { id } = useParams()
  const navigate = useNavigate()
  const [bounty, setBounty] = useState(null)
  const [loading, setLoading] = useState(true)
  const [showApply, setShowApply] = useState(false)
  const [applyForm, setApplyForm] = useState({ proposal: '', estimated_days: 7, quoted_price: 100, portfolio: '' })
  const [deliveryDesc, setDeliveryDesc] = useState('')
  const [deliveryFile, setDeliveryFile] = useState(null)

  useEffect(() => {
    loadBounty()
  }, [id])

  const loadBounty = async () => {
    setLoading(true)
    try {
      const data = await getBounty(id)
      setBounty(data)
    } catch { setBounty(null) }
    setLoading(false)
  }

  const handleApply = async (e) => {
    e.preventDefault()
    if (!authToken) return
    try {
      await applyForBounty(id, applyForm, authToken)
      setShowApply(false)
      loadBounty()
    } catch (err) {
      alert(err.detail || err.message || '竞标失败')
    }
  }

  const handleSelectDeveloper = async (appId) => {
    if (!authToken) return
    try {
      await selectBountyDeveloper(id, appId, authToken)
      loadBounty()
    } catch (err) {
      alert(err.detail || err.message || '选择失败')
    }
  }

  const handleDeliver = async () => {
    if (!authToken) return
    try {
      await deliverBounty(id, deliveryDesc, deliveryFile, authToken)
      setDeliveryDesc('')
      setDeliveryFile(null)
      loadBounty()
    } catch (err) {
      alert(err.detail || err.message || '交付失败')
    }
  }

  const handleReview = async (deliveryId, accept) => {
    if (!authToken) return
    try {
      await reviewBountyDelivery(id, deliveryId, accept, authToken)
      loadBounty()
    } catch (err) {
      alert(err.detail || err.message || '审核失败')
    }
  }

  const handleDeleteBounty = async () => {
    if (!confirm('确定删除此悬赏？此操作不可恢复。')) return
    try {
      await deleteBounty(id, authToken)
      navigate('/bounties')
    } catch (err) {
      alert(err.detail || err.message || '删除失败')
    }
  }

  if (loading) {
    return <div className="detail-page"><div className="detail-skeleton"><div className="skeleton-line shimmer" style={{ width: '40%', height: '32px' }} /><div className="skeleton-line shimmer" style={{ width: '80%' }} /></div></div>
  }

  if (!bounty) {
    return <div className="detail-page"><div className="empty-state"><h3>悬赏不存在</h3><button className="btn btn-primary" onClick={() => navigate('/bounties')}>返回悬赏市场</button></div></div>
  }

  const isPoster = bounty.poster_id === userId
  const isSelectedDev = bounty.selected_developer_id === userId
  const statusInfo = STATUS_MAP[bounty.status] || { label: bounty.status, color: '#71717a' }

  return (
    <div className="detail-page">
      <div className="detail-breadcrumb">
        <Link to="/"><Home size={14} /> 首页</Link>
        <ChevronRight size={14} />
        <Link to="/bounties">悬赏市场</Link>
        <ChevronRight size={14} />
        <span className="detail-breadcrumb-current">{bounty.title}</span>
      </div>

      <div className="bounty-detail-layout">
        <div className="bounty-detail-main">
          <div className="bounty-detail-header">
            <div>
              <h1>{bounty.title}</h1>
              <div className="bounty-detail-meta">
                <span className="bounty-status" style={{ backgroundColor: statusInfo.color }}>{statusInfo.label}</span>
                <span className="bounty-category-tag">{bounty.category}</span>
                <span className="bounty-type-tag">{bounty.skill_type}</span>
              </div>
            </div>
            {(isPoster) && authToken && (
              <button className="btn btn-danger btn-sm" onClick={handleDeleteBounty}>
                <Trash2 size={14} /> 删除悬赏
              </button>
            )}
          </div>

          <div className="detail-section">
            <h2>任务描述</h2>
            <p className="detail-description">{bounty.description}</p>
          </div>

          {bounty.requirements && (
            <div className="detail-section">
              <h2>额外要求</h2>
              <p className="detail-description">{bounty.requirements}</p>
            </div>
          )}

          <div className="bounty-info-grid">
            <div className="bounty-info-card">
              <DollarSign size={20} />
              <div>
                <span className="bounty-info-label">预算范围</span>
                <span className="bounty-info-value">{bounty.budget_min} - {bounty.budget_max} 金币</span>
              </div>
            </div>
            {bounty.deadline && (
              <div className="bounty-info-card">
                <Clock size={20} />
                <div>
                  <span className="bounty-info-label">截止日期</span>
                  <span className="bounty-info-value">{bounty.deadline}</span>
                </div>
              </div>
            )}
            {bounty.final_price && (
              <div className="bounty-info-card">
                <DollarSign size={20} />
                <div>
                  <span className="bounty-info-label">成交价格</span>
                  <span className="bounty-info-value">{bounty.final_price} 金币</span>
                </div>
              </div>
            )}
          </div>

          {/* Applications */}
          {bounty.applications && bounty.applications.length > 0 && (
            <div className="detail-section">
              <h2>竞标方案 ({bounty.applications.length})</h2>
              <div className="bounty-applications">
                {bounty.applications.map(app => (
                  <div key={app.id} className={`bounty-application ${app.status}`}>
                    <div className="bounty-app-header">
                      <span className="bounty-app-developer">{app.developer_name || '开发者'}</span>
                      <span className="bounty-app-price">{app.quoted_price} 金币</span>
                      <span className="bounty-app-days">{app.estimated_days} 天</span>
                      <span className={`bounty-app-status ${app.status}`}>
                        {app.status === 'pending' ? '待选' : app.status === 'accepted' ? '已选中' : '已拒绝'}
                      </span>
                    </div>
                    <p className="bounty-app-proposal">{app.proposal}</p>
                    {isPoster && bounty.status === 'open' && app.status === 'pending' && (
                      <button className="btn btn-sm btn-primary" onClick={() => handleSelectDeveloper(app.id)}>
                        选择此开发者
                      </button>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Apply form */}
          {authToken && bounty.status === 'open' && !isPoster && (
            <div className="detail-section">
              <h2>竞标接单</h2>
              {showApply ? (
                <form className="bounty-apply-form" onSubmit={handleApply}>
                  <div className="form-group">
                    <label>你的方案</label>
                    <textarea className="form-textarea" rows={4}
                      placeholder="描述你的实现思路、技术方案、相关经验"
                      value={applyForm.proposal}
                      onChange={e => setApplyForm({ ...applyForm, proposal: e.target.value })} required />
                  </div>
                  <div className="form-row">
                    <div className="form-group">
                      <label>报价（金币）</label>
                      <input className="form-input" type="number" min={1}
                        value={applyForm.quoted_price}
                        onChange={e => setApplyForm({ ...applyForm, quoted_price: +e.target.value })} required />
                    </div>
                    <div className="form-group">
                      <label>预计工期（天）</label>
                      <input className="form-input" type="number" min={1}
                        value={applyForm.estimated_days}
                        onChange={e => setApplyForm({ ...applyForm, estimated_days: +e.target.value })} required />
                    </div>
                  </div>
                  <div className="form-group">
                    <label>作品集/案例链接</label>
                    <input className="form-input" placeholder="GitHub 或其他作品链接"
                      value={applyForm.portfolio}
                      onChange={e => setApplyForm({ ...applyForm, portfolio: e.target.value })} />
                  </div>
                  <div className="form-actions">
                    <button type="button" className="btn btn-secondary" onClick={() => setShowApply(false)}>取消</button>
                    <button type="submit" className="btn btn-primary"><Send size={14} /> 提交竞标</button>
                  </div>
                </form>
              ) : (
                <button className="btn btn-primary" onClick={() => setShowApply(true)}>
                  <Send size={16} /> 我要竞标
                </button>
              )}
            </div>
          )}

          {/* Deliver section for selected developer */}
          {authToken && isSelectedDev && (bounty.status === 'in_progress') && (
            <div className="detail-section">
              <h2>交付技能</h2>
              <div className="bounty-deliver-form">
                <div className="form-group">
                  <label>交付说明</label>
                  <textarea className="form-textarea" rows={3}
                    placeholder="描述交付内容、使用方法等"
                    value={deliveryDesc}
                    onChange={e => setDeliveryDesc(e.target.value)} />
                </div>
                <div className="form-group">
                  <label>技能文件（可选）</label>
                  <input className="form-input" type="file"
                    onChange={e => setDeliveryFile(e.target.files[0])} />
                </div>
                <button className="btn btn-primary" onClick={handleDeliver}>
                  提交交付
                </button>
              </div>
            </div>
          )}

          {/* Deliveries for poster to review */}
          {isPoster && bounty.deliveries && bounty.deliveries.length > 0 && (
            <div className="detail-section">
              <h2>交付物</h2>
              {bounty.deliveries.map(d => (
                <div key={d.id} className={`bounty-delivery ${d.status}`}>
                  <div className="bounty-delivery-header">
                    <span>开发者: {d.developer_name || '匿名'}</span>
                    <span className={`bounty-app-status ${d.status}`}>
                      {d.status === 'pending' ? '待审核' : d.status === 'accepted' ? '已通过' : '已拒绝'}
                    </span>
                  </div>
                  {d.description && <p>{d.description}</p>}
                  {d.status === 'pending' && bounty.status === 'delivered' && (
                    <div className="bounty-review-actions">
                      <button className="btn btn-sm btn-primary" onClick={() => handleReview(d.id, true)}>
                        <CheckCircle size={14} /> 验收通过
                      </button>
                      <button className="btn btn-sm btn-danger" onClick={() => handleReview(d.id, false)}>
                        <XCircle size={14} /> 驳回
                      </button>
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
