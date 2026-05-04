import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { Package, Bot, Zap, Clock, Target, Plus, Play, Trash2, Calendar, Coins, CheckCircle, Settings, ExternalLink } from 'lucide-react'
import { getLibrary, getMyAgents, createAgent, runAgent, deleteAgent, getAgentRuns, getMyCronSubscriptions } from '../services/api'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'

const TABS = [
  { key: 'agents', label: '我的智能体', icon: Bot },
  { key: 'skills', label: '已购技能', icon: Zap },
  { key: 'crons', label: 'Cron订阅', icon: Clock },
  { key: 'bounties', label: '悬赏任务', icon: Target },
]

export default function MyLibraryPage({ userId, authToken }) {
  const navigate = useNavigate()
  const [activeTab, setActiveTab] = useState('agents')
  const [items, setItems] = useState([])
  const [agents, setAgents] = useState([])
  const [crons, setCrons] = useState([])
  const [loading, setLoading] = useState(true)
  const [showCreateAgent, setShowCreateAgent] = useState(false)
  const [newAgent, setNewAgent] = useState({ name: '', description: '', system_prompt: '', skill_ids: [] })
  const [runResult, setRunResult] = useState(null)
  const [agentRuns, setAgentRuns] = useState([])
  const [selectedAgent, setSelectedAgent] = useState(null)

  useEffect(() => {
    loadData()
  }, [userId, authToken, activeTab])

  const loadData = async () => {
    setLoading(true)
    try {
      // Always load library items (needed for skill assembly in agent tab)
      const libPromise = userId ? getLibrary(userId).catch(() => ({ items: [] })) : Promise.resolve({ items: [] })
      const agentsPromise = authToken ? getMyAgents(authToken).catch(() => []) : Promise.resolve([])
      const cronsPromise = authToken ? getMyCronSubscriptions(authToken).catch(() => []) : Promise.resolve([])

      const [libData, agentsData, cronsData] = await Promise.all([libPromise, agentsPromise, cronsPromise])
      setItems(libData.items || libData.library || libData.data || [])
      setAgents(Array.isArray(agentsData) ? agentsData : [])
      setCrons(Array.isArray(cronsData) ? cronsData : [])
    } catch { /* ignore */ }
    setLoading(false)
  }

  const handleCreateAgent = async () => {
    if (!newAgent.name || !authToken) return
    try {
      await createAgent(newAgent, authToken)
      setShowCreateAgent(false)
      setNewAgent({ name: '', description: '', system_prompt: '', skill_ids: [] })
      loadData()
    } catch { /* ignore */ }
  }

  const handleRunAgent = async (agentId) => {
    if (!authToken) return
    setRunResult({ agentId, loading: true })
    try {
      const res = await runAgent(agentId, '', authToken)
      setRunResult({ agentId, loading: false, output: res.output, status: res.status })
      // Show runs
      const runs = await getAgentRuns(agentId, 5, authToken).catch(() => [])
      setAgentRuns(Array.isArray(runs) ? runs : [])
    } catch {
      setRunResult({ agentId, loading: false, output: '执行失败', status: 'failed' })
    }
  }

  const handleDeleteAgent = async (agentId) => {
    if (!authToken) return
    try {
      await deleteAgent(agentId, authToken)
      loadData()
    } catch { /* ignore */ }
  }

  const toggleSkillForAgent = (productId) => {
    setNewAgent(prev => {
      const ids = prev.skill_ids.includes(productId)
        ? prev.skill_ids.filter(id => id !== productId)
        : [...prev.skill_ids, productId]
      return { ...prev, skill_ids: ids }
    })
  }

  const catConfig = {
    Agent: { emoji: '🤖', css: 'cat-agent' },
    Skill: { emoji: '⚡', css: 'cat-skill' },
    Cron: { emoji: '⏰', css: 'cat-cron' },
    Workflow: { emoji: '🔄', css: 'cat-workflow' },
  }

  return (
    <div className="library-page" style={{ maxWidth: 1200, margin: '0 auto', padding: 24 }}>
      <h1 className="page-title" style={{ marginBottom: 24 }}>
        <Package size={28} />
        我的库
      </h1>

      {/* Tabs */}
      <div style={{ display: 'flex', gap: 4, marginBottom: 24, borderBottom: '1px solid var(--border)', paddingBottom: 8 }}>
        {TABS.map(tab => (
          <button
            key={tab.key}
            onClick={() => setActiveTab(tab.key)}
            style={{
              display: 'flex', alignItems: 'center', gap: 6, padding: '8px 16px',
              background: activeTab === tab.key ? 'var(--accent-primary)' : 'transparent',
              color: activeTab === tab.key ? 'white' : 'var(--text-secondary)',
              border: 'none', borderRadius: 8, cursor: 'pointer', fontSize: 14, fontWeight: 500,
            }}
          >
            <tab.icon size={16} />
            {tab.label}
          </button>
        ))}
      </div>

      {/* Agents Tab */}
      {activeTab === 'agents' && (
        <div>
          <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 16 }}>
            <h2 style={{ fontSize: 18, fontWeight: 600, color: 'var(--text-primary)' }}>我的智能体</h2>
            {authToken && (
              <button className="btn btn-primary btn-sm" onClick={() => setShowCreateAgent(true)}>
                <Plus size={16} /> 创建智能体
              </button>
            )}
          </div>

          {/* Create Agent Form */}
          {showCreateAgent && (
            <div style={{ background: 'var(--bg-card)', border: '1px solid var(--border)', borderRadius: 12, padding: 20, marginBottom: 16 }}>
              <h3 style={{ marginBottom: 12, color: 'var(--text-primary)' }}>创建新智能体</h3>
              <input placeholder="智能体名称" value={newAgent.name} onChange={e => setNewAgent(p => ({ ...p, name: e.target.value }))}
                style={{ width: '100%', padding: 10, background: 'var(--bg-base)', border: '1px solid var(--border)', borderRadius: 8, color: 'var(--text-primary)', marginBottom: 8, outline: 'none' }} />
              <input placeholder="描述（可选）" value={newAgent.description} onChange={e => setNewAgent(p => ({ ...p, description: e.target.value }))}
                style={{ width: '100%', padding: 10, background: 'var(--bg-base)', border: '1px solid var(--border)', borderRadius: 8, color: 'var(--text-primary)', marginBottom: 8, outline: 'none' }} />
              <textarea placeholder="System Prompt（可选）" rows={3} value={newAgent.system_prompt} onChange={e => setNewAgent(p => ({ ...p, system_prompt: e.target.value }))}
                style={{ width: '100%', padding: 10, background: 'var(--bg-base)', border: '1px solid var(--border)', borderRadius: 8, color: 'var(--text-primary)', marginBottom: 8, outline: 'none', resize: 'vertical' }} />
              {items.length > 0 && (
                <div style={{ marginBottom: 12 }}>
                  <p style={{ fontSize: 13, color: 'var(--text-secondary)', marginBottom: 6 }}>装配已购技能：</p>
                  <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
                    {items.map(item => {
                      const selected = newAgent.skill_ids.includes(item.product_id || item.id)
                      return (
                        <button key={item.product_id || item.id} onClick={() => toggleSkillForAgent(item.product_id || item.id)}
                          style={{ padding: '4px 10px', borderRadius: 6, fontSize: 12, border: '1px solid', cursor: 'pointer',
                            background: selected ? 'var(--accent-primary)' : 'transparent',
                            color: selected ? 'white' : 'var(--text-secondary)',
                            borderColor: selected ? 'var(--accent-primary)' : 'var(--border)' }}>
                          {(catConfig[item.category]?.emoji || '📦')} {item.name || item.product_name}
                        </button>
                      )
                    })}
                  </div>
                </div>
              )}
              <div style={{ display: 'flex', gap: 8 }}>
                <button className="btn btn-primary btn-sm" onClick={handleCreateAgent} disabled={!newAgent.name}>创建</button>
                <button className="btn btn-ghost btn-sm" onClick={() => setShowCreateAgent(false)}>取消</button>
              </div>
            </div>
          )}

          {loading ? (
            <div style={{ color: 'var(--text-secondary)', textAlign: 'center', padding: 40 }}>加载中...</div>
          ) : agents.length === 0 ? (
            <div className="empty-state">
              <span className="empty-icon">🤖</span>
              <h3>还没有创建智能体</h3>
              <p>装配已购买的Skill，创建自定义智能体</p>
              {authToken && <button className="btn btn-primary" onClick={() => setShowCreateAgent(true)}>创建智能体</button>}
            </div>
          ) : (
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(340px, 1fr))', gap: 16 }}>
              {agents.map(agent => (
                <div key={agent.id} style={{ background: 'var(--bg-card)', border: '1px solid var(--border)', borderRadius: 12, padding: 20 }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 8 }}>
                    <h3 style={{ color: 'var(--text-primary)', fontSize: 16, fontWeight: 600 }}>{agent.name}</h3>
                    <span style={{ fontSize: 12, color: agent.status === 'active' ? '#22c55e' : 'var(--text-secondary)' }}>
                      {agent.status === 'active' ? '活跃' : '停止'}
                    </span>
                  </div>
                  {agent.description && <p style={{ fontSize: 13, color: 'var(--text-secondary)', marginBottom: 8 }}>{agent.description}</p>}
                  {agent.skills && agent.skills.length > 0 && (
                    <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4, marginBottom: 12 }}>
                      {agent.skills.map(s => (
                        <span key={s.id} style={{ padding: '2px 8px', borderRadius: 4, fontSize: 11, background: 'rgba(99,102,241,0.1)', color: 'var(--accent-primary)' }}>
                          {s.name}
                        </span>
                      ))}
                    </div>
                  )}
                  <div style={{ fontSize: 12, color: 'var(--text-secondary)', marginBottom: 12 }}>
                    执行 {agent.runs_count || 0} 次 {agent.last_run_at ? `· 最后: ${new Date(agent.last_run_at).toLocaleString('zh-CN')}` : ''}
                  </div>
                  {runResult?.agentId === agent.id && runResult.loading && (
                    <div style={{ background: 'rgba(99,102,241,0.08)', border: '1px solid rgba(99,102,241,0.2)', borderRadius: 8, padding: 12, marginBottom: 12, fontSize: 13, color: 'var(--accent-primary)', animation: 'thinkingPulse 1.5s ease-in-out infinite' }}>
                      正在执行，请稍候...
                    </div>
                  )}
                  {runResult?.agentId === agent.id && !runResult.loading && runResult.output && (
                    <div style={{ background: 'var(--bg-base)', border: '1px solid var(--border)', borderRadius: 8, padding: 12, marginBottom: 12, fontSize: 13, color: 'var(--text-primary)', maxHeight: 200, overflow: 'auto' }}>
                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 6 }}>
                        <span style={{ fontSize: 11, color: 'var(--text-secondary)' }}>执行结果 {runResult.status === 'success' ? '✅' : '❌'}</span>
                        <button onClick={() => setRunResult(null)} style={{ background: 'none', border: 'none', color: 'var(--text-muted)', cursor: 'pointer', fontSize: 12 }}>关闭</button>
                      </div>
                      <ReactMarkdown remarkPlugins={[remarkGfm]}>{runResult.output.slice(0, 1000)}</ReactMarkdown>
                    </div>
                  )}
                  <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
                    <button className="btn btn-primary btn-sm" onClick={() => handleRunAgent(agent.id)} disabled={runResult?.agentId === agent.id && runResult.loading}>
                      <Play size={14} /> {runResult?.agentId === agent.id && runResult.loading ? '执行中...' : '运行'}
                    </button>
                    {agent.runs_count > 0 && (
                      <button className="btn btn-ghost btn-sm" onClick={() => setRunResult(prev => prev?.agentId === agent.id ? null : { agentId: agent.id, loading: false, output: `查看最近 ${agent.runs_count} 次执行记录`, status: 'info' })} style={{ fontSize: 12 }}>
                        <ExternalLink size={12} /> 执行记录
                      </button>
                    )}
                    <button className="btn btn-ghost btn-sm" onClick={() => handleDeleteAgent(agent.id)} style={{ marginLeft: 'auto' }}>
                      <Trash2 size={14} />
                    </button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Skills Tab */}
      {activeTab === 'skills' && (
        <div>
          <h2 style={{ fontSize: 18, fontWeight: 600, color: 'var(--text-primary)', marginBottom: 16 }}>已购技能</h2>
          {loading ? (
            <div style={{ color: 'var(--text-secondary)', textAlign: 'center', padding: 40 }}>加载中...</div>
          ) : items.length === 0 ? (
            <div className="empty-state">
              <span className="empty-icon">📦</span>
              <h3>还没有购买任何商品</h3>
              <p>去逛逛吧，发现优质的 AI 工具</p>
              <button className="btn btn-primary" onClick={() => navigate('/')}>浏览市场</button>
            </div>
          ) : (
            <div className="library-grid">
              {items.map((item) => {
                const cat = catConfig[item.category] || { emoji: '📦', css: 'cat-default' }
                return (
                  <div key={item.id || item.product_id} className="library-card" onClick={() => navigate(`/product/${item.product_id || item.id}`)}>
                    <div className="library-card-badge"><CheckCircle size={10} /> 已购买</div>
                    <div className="library-card-header">
                      <div className={`library-card-icon product-icon-wrapper ${cat.css}`}>{cat.emoji}</div>
                      <h3>{item.name || item.product_name}</h3>
                    </div>
                    {item.description && <p className="library-card-desc">{item.description}</p>}
                    <div className="library-card-meta">
                      <span><Calendar size={13} /> {item.purchased_at ? new Date(item.purchased_at).toLocaleDateString('zh-CN') : '未知日期'}</span>
                      <span><Coins size={13} /> {item.price_paid ?? item.price ?? '-'} 金币</span>
                    </div>
                  </div>
                )
              })}
            </div>
          )}
        </div>
      )}

      {/* Crons Tab */}
      {activeTab === 'crons' && (
        <div>
          <h2 style={{ fontSize: 18, fontWeight: 600, color: 'var(--text-primary)', marginBottom: 16 }}>Cron订阅</h2>
          {loading ? (
            <div style={{ color: 'var(--text-secondary)', textAlign: 'center', padding: 40 }}>加载中...</div>
          ) : crons.length === 0 ? (
            <div className="empty-state">
              <span className="empty-icon">⏰</span>
              <h3>还没有订阅定时任务</h3>
              <p>浏览市场中的Cron商品，订阅自动化任务</p>
              <button className="btn btn-primary" onClick={() => navigate('/')}>浏览市场</button>
            </div>
          ) : (
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(340px, 1fr))', gap: 16 }}>
              {crons.map(sub => (
                <div key={sub.id} style={{ background: 'var(--bg-card)', border: '1px solid var(--border)', borderRadius: 12, padding: 20 }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 8 }}>
                    <h3 style={{ color: 'var(--text-primary)', fontSize: 16 }}>{sub.product_name || 'Cron任务'}</h3>
                    <span style={{ fontSize: 12, color: sub.status === 'active' ? '#22c55e' : '#f59e0b' }}>
                      {sub.status === 'active' ? '活跃' : '过期'}
                    </span>
                  </div>
                  <div style={{ fontSize: 13, color: 'var(--text-secondary)' }}>
                    调度: <code style={{ background: 'var(--bg-base)', padding: '2px 6px', borderRadius: 4 }}>{sub.schedule_cron}</code>
                  </div>
                  <div style={{ fontSize: 12, color: 'var(--text-secondary)', marginTop: 4 }}>
                    月费: {sub.monthly_price} 币 · 执行 {sub.execution_count || 0} 次
                  </div>
                  {sub.expires_at && (
                    <div style={{ fontSize: 12, color: 'var(--text-secondary)', marginTop: 4 }}>
                      到期: {new Date(sub.expires_at).toLocaleDateString('zh-CN')}
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Bounties Tab */}
      {activeTab === 'bounties' && (
        <div>
          <h2 style={{ fontSize: 18, fontWeight: 600, color: 'var(--text-primary)', marginBottom: 16 }}>悬赏任务</h2>
          <div className="empty-state">
            <span className="empty-icon">🎯</span>
            <h3>暂无承接的悬赏任务</h3>
            <p>浏览悬赏市场，承接开发任务</p>
            <button className="btn btn-primary" onClick={() => navigate('/bounties')}>浏览悬赏</button>
          </div>
        </div>
      )}
    </div>
  )
}
