import { useState, useEffect } from 'react'
import { useNavigate, Link } from 'react-router-dom'
import { Plus, Search, Filter, Clock, DollarSign, Users, ChevronRight, Trash2 } from 'lucide-react'
import { getBounties, createBounty, deleteBounty } from '../services/api'

const STATUS_MAP = {
  open: { label: '招募中', color: '#22c55e' },
  in_progress: { label: '开发中', color: '#3b82f6' },
  delivered: { label: '已交付', color: '#f59e0b' },
  completed: { label: '已完成', color: '#6366f1' },
  cancelled: { label: '已取消', color: '#ef4444' },
}

export default function BountyPage({ userId, authToken }) {
  const navigate = useNavigate()
  const [bounties, setBounties] = useState([])
  const [loading, setLoading] = useState(true)
  const [statusFilter, setStatusFilter] = useState('open')
  const [keyword, setKeyword] = useState('')
  const [showCreate, setShowCreate] = useState(false)
  const [form, setForm] = useState({
    title: '', description: '', category: 'Skill',
    budget_min: 100, budget_max: 500,
    deadline: '', skill_type: 'prompt', requirements: '',
  })

  useEffect(() => {
    loadBounties()
  }, [statusFilter])

  const loadBounties = async () => {
    setLoading(true)
    try {
      const res = await getBounties({ status: statusFilter || undefined, keyword: keyword || undefined })
      setBounties(res.bounties || [])
    } catch { setBounties([]) }
    setLoading(false)
  }

  const handleCreate = async (e) => {
    e.preventDefault()
    if (!authToken) { navigate('/'); return }
    try {
      const data = { ...form, tags: [] }
      await createBounty(data, authToken)
      setShowCreate(false)
      setForm({ title: '', description: '', category: 'Skill', budget_min: 100, budget_max: 500, deadline: '', skill_type: 'prompt', requirements: '' })
      loadBounties()
    } catch (err) {
      alert(err.detail || err.message || '创建失败')
    }
  }

  const handleDelete = async (e, bountyId) => {
    e.preventDefault()
    e.stopPropagation()
    if (!confirm('确定删除此悬赏？')) return
    try {
      await deleteBounty(bountyId, authToken)
      loadBounties()
    } catch (err) {
      alert(err.detail || err.message || '删除失败')
    }
  }

  return (
    <div className="bounty-page">
      <div className="bounty-header">
        <div>
          <h1>悬赏任务市场</h1>
          <p className="bounty-subtitle">发布需求，开发者接单，技能交易</p>
        </div>
        {authToken && (
          <button className="btn btn-primary" onClick={() => setShowCreate(!showCreate)}>
            <Plus size={16} /> 发布悬赏
          </button>
        )}
      </div>

      {showCreate && (
        <form className="bounty-create-form" onSubmit={handleCreate}>
          <h3>发布悬赏任务</h3>
          <div className="form-group">
            <label>任务标题</label>
            <input className="form-input" placeholder="如：开发一个加密货币行情分析Agent"
              value={form.title} onChange={e => setForm({ ...form, title: e.target.value })} required />
          </div>
          <div className="form-group">
            <label>详细描述</label>
            <textarea className="form-textarea" rows={4}
              placeholder="描述你需要的功能、性能要求、使用场景等"
              value={form.description} onChange={e => setForm({ ...form, description: e.target.value })} required />
          </div>
          <div className="form-row">
            <div className="form-group">
              <label>分类</label>
              <select className="form-input" value={form.category}
                onChange={e => setForm({ ...form, category: e.target.value })}>
                <option value="Agent">Agent</option>
                <option value="Skill">Skill</option>
                <option value="Cron">Cron</option>
                <option value="Workflow">Workflow</option>
              </select>
            </div>
            <div className="form-group">
              <label>技能类型</label>
              <select className="form-input" value={form.skill_type}
                onChange={e => setForm({ ...form, skill_type: e.target.value })}>
                <option value="prompt">Prompt 提示词</option>
                <option value="code">Code 代码</option>
                <option value="sdk">SDK 接口</option>
              </select>
            </div>
          </div>
          <div className="form-row">
            <div className="form-group">
              <label>最低预算（金币）</label>
              <input className="form-input" type="number" min={1}
                value={form.budget_min} onChange={e => setForm({ ...form, budget_min: +e.target.value })} required />
            </div>
            <div className="form-group">
              <label>最高预算（金币）</label>
              <input className="form-input" type="number" min={form.budget_min}
                value={form.budget_max} onChange={e => setForm({ ...form, budget_max: +e.target.value })} required />
            </div>
          </div>
          <div className="form-group">
            <label>截止日期</label>
            <input className="form-input" type="date"
              value={form.deadline} onChange={e => setForm({ ...form, deadline: e.target.value })} />
          </div>
          <div className="form-group">
            <label>额外要求</label>
            <textarea className="form-textarea" rows={2}
              placeholder="如：必须支持多语言、需要提供文档等"
              value={form.requirements} onChange={e => setForm({ ...form, requirements: e.target.value })} />
          </div>
          <div className="form-actions">
            <button type="button" className="btn btn-secondary" onClick={() => setShowCreate(false)}>取消</button>
            <button type="submit" className="btn btn-primary">发布悬赏</button>
          </div>
        </form>
      )}

      <div className="bounty-filters">
        <div className="bounty-search">
          <Search size={16} />
          <input placeholder="搜索悬赏任务..." value={keyword}
            onChange={e => setKeyword(e.target.value)}
            onKeyDown={e => e.key === 'Enter' && loadBounties()} />
        </div>
        <div className="bounty-tabs">
          {['open', 'in_progress', 'completed', ''].map(s => (
            <button key={s} className={`bounty-tab ${statusFilter === s ? 'active' : ''}`}
              onClick={() => setStatusFilter(s)}>
              {s === '' ? '全部' : STATUS_MAP[s]?.label || s}
            </button>
          ))}
        </div>
      </div>

      {loading ? (
        <div className="loading-skeleton">
          {[1, 2, 3].map(i => <div key={i} className="skeleton-card shimmer" />)}
        </div>
      ) : bounties.length === 0 ? (
        <div className="empty-state">
          <span className="empty-icon">📋</span>
          <h3>暂无悬赏任务</h3>
          <p>发布一个悬赏，让开发者为你定制技能</p>
        </div>
      ) : (
        <div className="bounty-list">
          {bounties.map(b => (
            <Link to={`/bounty/${b.id}`} key={b.id} className="bounty-card">
              <div className="bounty-card-header">
                <h3>{b.title}</h3>
                {authToken && b.poster_id === userId && (
                  <button className="btn btn-ghost btn-sm" style={{ padding: '4px', minWidth: 'auto' }}
                    title="删除" onClick={(e) => handleDelete(e, b.id)}>
                    <Trash2 size={16} style={{ color: '#ef4444' }} />
                  </button>
                )}
                <span className="bounty-status" style={{ backgroundColor: STATUS_MAP[b.status]?.color || '#71717a' }}>
                  {STATUS_MAP[b.status]?.label || b.status}
                </span>
              </div>
              <p className="bounty-card-desc">{b.description?.slice(0, 120)}{b.description?.length > 120 ? '...' : ''}</p>
              <div className="bounty-card-meta">
                <span className="bounty-budget">
                  <DollarSign size={14} /> {b.budget_min} - {b.budget_max} 金币
                </span>
                <span className="bounty-category-tag">{b.category}</span>
                <span className="bounty-type-tag">{b.skill_type}</span>
                {b.application_count > 0 && (
                  <span className="bounty-applicants"><Users size={14} /> {b.application_count} 人竞标</span>
                )}
                {b.deadline && (
                  <span className="bounty-deadline"><Clock size={14} /> {b.deadline}</span>
                )}
              </div>
              <div className="bounty-card-footer">
                <span className="bounty-poster">by {b.poster_name || '匿名'}</span>
                <ChevronRight size={16} className="bounty-arrow" />
              </div>
            </Link>
          ))}
        </div>
      )}
    </div>
  )
}
