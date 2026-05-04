import { useState, useEffect } from 'react'
import {
  BarChart3, Target, Package, Users, ShieldAlert,
  RefreshCw, CheckCircle, XCircle, Ban, Eye
} from 'lucide-react'
import {
  adminGetAnalytics, adminGetBounties, adminUpdateBountyStatus,
  adminGetSkills, adminUpdateSkillStatus, adminGetUsers,
  adminUpdateUserStatus, adminScanRisks
} from '../services/api'

const TABS = [
  { key: 'overview', label: '概览', icon: BarChart3 },
  { key: 'bounties', label: '悬赏管理', icon: Target },
  { key: 'skills', label: 'Skill管理', icon: Package },
  { key: 'users', label: '用户管理', icon: Users },
  { key: 'risks', label: '风险扫描', icon: ShieldAlert },
]

export default function AdminPage({ authToken }) {
  const [tab, setTab] = useState('overview')
  const [analytics, setAnalytics] = useState(null)
  const [bounties, setBounties] = useState([])
  const [bountyPage, setBountyPage] = useState(1)
  const [skills, setSkills] = useState([])
  const [skillPage, setSkillPage] = useState(1)
  const [users, setUsers] = useState([])
  const [userPage, setUserPage] = useState(1)
  const [risks, setRisks] = useState([])
  const [scanning, setScanning] = useState(false)
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    if (!authToken) return
    if (tab === 'overview') fetchAnalytics()
    else if (tab === 'bounties') fetchBounties()
    else if (tab === 'skills') fetchSkills()
    else if (tab === 'users') fetchUsers()
  }, [tab, authToken, bountyPage, skillPage, userPage])

  async function fetchAnalytics() {
    setLoading(true)
    try {
      const data = await adminGetAnalytics(authToken)
      setAnalytics(data)
    } catch { setAnalytics(null) }
    setLoading(false)
  }

  async function fetchBounties() {
    setLoading(true)
    try {
      const data = await adminGetBounties('', bountyPage, authToken)
      setBounties(data.bounties || data.items || [])
    } catch { setBounties([]) }
    setLoading(false)
  }

  async function fetchSkills() {
    setLoading(true)
    try {
      const data = await adminGetSkills(skillPage, authToken)
      setSkills(data.skills || data.items || [])
    } catch { setSkills([]) }
    setLoading(false)
  }

  async function fetchUsers() {
    setLoading(true)
    try {
      const data = await adminGetUsers(userPage, authToken)
      setUsers(data.users || data.items || [])
    } catch { setUsers([]) }
    setLoading(false)
  }

  async function handleBountyAction(bountyId, status) {
    try {
      await adminUpdateBountyStatus(bountyId, status, '', authToken)
      fetchBounties()
    } catch {}
  }

  async function handleSkillAction(skillId, status) {
    try {
      await adminUpdateSkillStatus(skillId, status, authToken)
      fetchSkills()
    } catch {}
  }

  async function handleUserAction(userId, status) {
    try {
      await adminUpdateUserStatus(userId, status, authToken)
      fetchUsers()
    } catch {}
  }

  async function handleScan() {
    setScanning(true)
    try {
      const data = await adminScanRisks(authToken)
      setRisks(data.risks || data.items || [])
    } catch { setRisks([]) }
    setScanning(false)
  }

  function renderOverview() {
    const stats = analytics || {}
    const cards = [
      { label: '总用户', value: stats.total_users ?? '-', icon: Users },
      { label: '总商品', value: stats.total_products ?? '-', icon: Package },
      { label: '总交易', value: stats.total_transactions ?? '-', icon: BarChart3 },
      { label: '总交易额', value: stats.total_volume ?? '-', icon: Target },
      { label: '总Skills', value: stats.total_skills ?? '-', icon: Eye },
    ]
    return (
      <div className="admin-stats-grid">
        {cards.map((c) => (
          <div className="admin-stat-card" key={c.label}>
            <c.icon size={24} style={{ color: 'var(--accent-primary)' }} />
            <div>
              <div className="stat-value">{c.value}</div>
              <div className="stat-label">{c.label}</div>
            </div>
          </div>
        ))}
      </div>
    )
  }

  function renderBounties() {
    return (
      <div className="admin-table-wrapper">
        <table className="admin-table">
          <thead>
            <tr>
              <th>ID</th><th>标题</th><th>发布者</th><th>分类</th><th>预算</th><th>状态</th><th>操作</th>
            </tr>
          </thead>
          <tbody>
            {bounties.length === 0 && !loading && (
              <tr><td colSpan={7} style={{ textAlign: 'center', padding: 32 }}>暂无数据</td></tr>
            )}
            {bounties.map((b) => (
              <tr key={b.id || b.bounty_id}>
                <td>{b.id || b.bounty_id}</td>
                <td>{b.title}</td>
                <td>{b.poster_name || b.poster_id || '-'}</td>
                <td>{b.category || '-'}</td>
                <td>{b.budget ?? b.budget_coins ?? '-'}</td>
                <td><span className={`status-badge ${b.status === 'active' || b.status === 'open' ? 'active' : 'inactive'}`}>{b.status}</span></td>
                <td>
                  <div className="admin-actions">
                    <button className="btn btn-sm btn-relist" onClick={() => handleBountyAction(b.id || b.bounty_id, 'approved')}><CheckCircle size={12} /> 通过</button>
                    <button className="btn btn-sm btn-delist" onClick={() => handleBountyAction(b.id || b.bounty_id, 'rejected')}><XCircle size={12} /> 拒绝</button>
                    <button className="btn btn-sm btn-delist" onClick={() => handleBountyAction(b.id || b.bounty_id, 'takedown')}><Ban size={12} /> 下架</button>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        <div className="pagination" style={{ marginTop: 16 }}>
          <button className="page-btn" disabled={bountyPage <= 1} onClick={() => setBountyPage((p) => p - 1)}>上一页</button>
          <span style={{ color: 'var(--text-muted)', fontSize: 13 }}>第 {bountyPage} 页</span>
          <button className="page-btn" onClick={() => setBountyPage((p) => p + 1)}>下一页</button>
        </div>
      </div>
    )
  }

  function renderSkills() {
    return (
      <div className="admin-table-wrapper">
        <table className="admin-table">
          <thead>
            <tr>
              <th>ID</th><th>商品名</th><th>类型</th><th>大小</th><th>状态</th><th>操作</th>
            </tr>
          </thead>
          <tbody>
            {skills.length === 0 && !loading && (
              <tr><td colSpan={6} style={{ textAlign: 'center', padding: 32 }}>暂无数据</td></tr>
            )}
            {skills.map((s) => (
              <tr key={s.id || s.skill_id}>
                <td>{s.id || s.skill_id}</td>
                <td>{s.product_name || s.name || '-'}</td>
                <td>{s.skill_type || '-'}</td>
                <td>{s.file_size ? `${(s.file_size / 1024).toFixed(1)}KB` : '-'}</td>
                <td><span className={`status-badge ${s.status === 'active' || s.status === 'approved' ? 'active' : 'inactive'}`}>{s.status}</span></td>
                <td>
                  <div className="admin-actions">
                    <button className="btn btn-sm btn-relist" onClick={() => handleSkillAction(s.id || s.skill_id, 'approved')}><CheckCircle size={12} /> 通过</button>
                    <button className="btn btn-sm btn-delist" onClick={() => handleSkillAction(s.id || s.skill_id, 'takedown')}><Ban size={12} /> 下架</button>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        <div className="pagination" style={{ marginTop: 16 }}>
          <button className="page-btn" disabled={skillPage <= 1} onClick={() => setSkillPage((p) => p - 1)}>上一页</button>
          <span style={{ color: 'var(--text-muted)', fontSize: 13 }}>第 {skillPage} 页</span>
          <button className="page-btn" onClick={() => setSkillPage((p) => p + 1)}>下一页</button>
        </div>
      </div>
    )
  }

  function renderUsers() {
    return (
      <div className="admin-table-wrapper">
        <table className="admin-table">
          <thead>
            <tr>
              <th>ID</th><th>用户名</th><th>昵称</th><th>金币</th><th>角色</th><th>状态</th><th>操作</th>
            </tr>
          </thead>
          <tbody>
            {users.length === 0 && !loading && (
              <tr><td colSpan={7} style={{ textAlign: 'center', padding: 32 }}>暂无数据</td></tr>
            )}
            {users.map((u) => (
              <tr key={u.id || u.user_id}>
                <td>{u.id || u.user_id}</td>
                <td>{u.username || '-'}</td>
                <td>{u.nickname || '-'}</td>
                <td>{u.coins ?? u.balance ?? '-'}</td>
                <td>{u.role || '-'}</td>
                <td><span className={`status-badge ${u.status === 'active' ? 'active' : 'inactive'}`}>{u.status}</span></td>
                <td>
                  <div className="admin-actions">
                    <button className="btn btn-sm btn-delist" onClick={() => handleUserAction(u.id || u.user_id, 'banned')}><Ban size={12} /> 封禁</button>
                    <button className="btn btn-sm btn-relist" onClick={() => handleUserAction(u.id || u.user_id, 'active')}><CheckCircle size={12} /> 激活</button>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        <div className="pagination" style={{ marginTop: 16 }}>
          <button className="page-btn" disabled={userPage <= 1} onClick={() => setUserPage((p) => p - 1)}>上一页</button>
          <span style={{ color: 'var(--text-muted)', fontSize: 13 }}>第 {userPage} 页</span>
          <button className="page-btn" onClick={() => setUserPage((p) => p + 1)}>下一页</button>
        </div>
      </div>
    )
  }

  function renderRisks() {
    return (
      <div>
        <div style={{ marginBottom: 20 }}>
          <button className="btn btn-primary" disabled={scanning} onClick={handleScan}>
            <RefreshCw size={16} className={scanning ? 'spin' : ''} />
            {scanning ? '扫描中...' : '开始风险扫描'}
          </button>
        </div>
        {risks.length === 0 && !scanning && (
          <div className="empty-state" style={{ padding: 40 }}>
            <ShieldAlert size={48} style={{ color: 'var(--text-muted)', marginBottom: 12 }} />
            <p style={{ color: 'var(--text-secondary)' }}>点击上方按钮开始扫描</p>
          </div>
        )}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
          {risks.map((r, i) => (
            <div className="risk-card" key={i}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
                <strong style={{ fontSize: 15 }}>{r.product_name || r.title || `风险项 #${i + 1}`}</strong>
                <span className={`risk-badge ${r.risk_score >= 80 ? 'high' : r.risk_score >= 50 ? 'medium' : 'low'}`}>
                  风险分: {r.risk_score}
                </span>
              </div>
              {r.risk_tags && r.risk_tags.length > 0 && (
                <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', marginBottom: 8 }}>
                  {r.risk_tags.map((tag, j) => (
                    <span key={j} className="tag-pill" style={{ background: 'rgba(239,68,68,0.1)', color: '#ef4444', borderColor: 'rgba(239,68,68,0.15)' }}>{tag}</span>
                  ))}
                </div>
              )}
              <p style={{ fontSize: 13, color: 'var(--text-secondary)' }}>{r.reason || r.description || '-'}</p>
            </div>
          ))}
        </div>
      </div>
    )
  }

  if (!authToken) {
    return (
      <div className="admin-page">
        <div className="empty-state" style={{ padding: 80 }}>
          <ShieldAlert size={56} style={{ color: 'var(--text-muted)', marginBottom: 16 }} />
          <h3>需要管理员登录</h3>
          <p>请先登录管理员账号后访问此页面</p>
        </div>
      </div>
    )
  }

  return (
    <div className="admin-page">
      <div className="page-title">
        <ShieldAlert size={28} />
        管理后台
      </div>

      <div className="admin-tabs">
        {TABS.map((t) => (
          <button
            key={t.key}
            className={`admin-tab ${tab === t.key ? 'active' : ''}`}
            onClick={() => setTab(t.key)}
          >
            <t.icon size={16} />
            {t.label}
          </button>
        ))}
      </div>

      <div style={{ marginTop: 24 }}>
        {loading && <p style={{ color: 'var(--text-muted)', marginBottom: 12 }}>加载中...</p>}
        {tab === 'overview' && renderOverview()}
        {tab === 'bounties' && renderBounties()}
        {tab === 'skills' && renderSkills()}
        {tab === 'users' && renderUsers()}
        {tab === 'risks' && renderRisks()}
      </div>
    </div>
  )
}
