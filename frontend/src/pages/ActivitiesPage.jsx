import { useState, useEffect } from 'react'
import { Trophy, Gift, Calendar, TrendingUp, Coins } from 'lucide-react'
import { getActivities, doCheckin, claimTaskReward, getPointsBalance, redeemPoints, getLeaderboard } from '../services/api'

function LevelBadge({ level }) {
  const config = {
    1: { label: '新手', color: '#94a3b8' },
    2: { label: '熟手', color: '#22c55e' },
    3: { label: '专家', color: '#3b82f6' },
    4: { label: '大师', color: '#a855f7' },
    5: { label: '传奇', color: '#f59e0b' },
  }
  const c = config[level] || config[1]
  return <span style={{ background: c.color + '20', color: c.color, padding: '2px 8px', borderRadius: '4px', fontSize: '12px', fontWeight: 600 }}>Lv{level} {c.label}</span>
}

export default function ActivitiesPage({ userId, authToken, onLoginClick }) {
  const [activities, setActivities] = useState([])
  const [points, setPoints] = useState(null)
  const [leaderboard, setLeaderboard] = useState([])
  const [checkinResult, setCheckinResult] = useState(null)
  const [redeemAmount, setRedeemAmount] = useState('')
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    if (authToken) loadData()
  }, [authToken])

  const loadData = async () => {
    setLoading(true)
    try {
      const [acts, pts, lb] = await Promise.all([
        getActivities(authToken).catch(() => []),
        getPointsBalance(authToken).catch(() => null),
        getLeaderboard().catch(() => []),
      ])
      setActivities(acts.activities || acts || [])
      setPoints(pts)
      setLeaderboard(lb.leaderboard || lb || [])
    } finally {
      setLoading(false)
    }
  }

  const handleCheckin = async () => {
    if (!authToken) {
      setCheckinResult({ ok: false, message: '请先登录后再签到' })
      return
    }
    try {
      const res = await doCheckin(authToken)
      setCheckinResult(res)
      if (res.ok) loadData()
    } catch {
      setCheckinResult({ ok: false, message: '签到失败，请稍后重试' })
    }
  }

  const handleClaim = async (taskId) => {
    try {
      await claimTaskReward(taskId, authToken)
      loadData()
    } catch {
      // ignore
    }
  }

  const handleRedeem = async () => {
    const amount = parseInt(redeemAmount)
    if (!amount || amount <= 0) return
    try {
      await redeemPoints({ amount, redeem_type: 'coins' }, authToken)
      setRedeemAmount('')
      loadData()
    } catch {
      // ignore
    }
  }

  const allTasks = activities.flatMap((a) => a.tasks || [])

  return (
    <div className="activity-page">
      <div className="activity-header">
        <h1><Trophy size={28} style={{ marginRight: 12, verticalAlign: 'middle' }} />活动任务中心</h1>
        {points && (
          <div className="activity-points-badge">
            <LevelBadge level={points.level || 1} />
            <span>{points.balance || 0} 积分</span>
          </div>
        )}
      </div>

      {/* Check-in */}
      <div className="checkin-section">
        <h3 style={{ marginBottom: 16, color: 'var(--text-primary)' }}>
          <Calendar size={20} style={{ marginRight: 8, verticalAlign: 'middle' }} />
          每日签到
        </h3>
        <button className="checkin-btn" onClick={handleCheckin} disabled={loading}>
          {!authToken ? '登录后签到领积分' : '签到领积分'}
        </button>
        {points && (
          <div className="checkin-streak">
            连续签到 {points.continuous_checkin_days || 0} 天
            {(points.continuous_checkin_days || 0) >= 7 && <span style={{ color: '#f59e0b', marginLeft: 8 }}>满7天额外+50!</span>}
          </div>
        )}
        {checkinResult && (
          <div className={`checkin-result ${checkinResult.ok ? 'success' : 'already'}`}>
            {checkinResult.ok
              ? `签到成功！获得 ${checkinResult.points} 积分${checkinResult.bonus ? ` (含连续签到奖励 +${checkinResult.bonus})` : ''}`
              : checkinResult.message || '今天已签到'}
            {!authToken && checkinResult.message?.includes('登录') && (
              <button onClick={onLoginClick} style={{ marginLeft: 12, background: 'var(--accent-primary)', color: 'white', border: 'none', borderRadius: 6, padding: '4px 16px', cursor: 'pointer', fontSize: 13 }}>
                去登录
              </button>
            )}
          </div>
        )}
      </div>

      {/* Tasks Grid */}
      {allTasks.length > 0 && (
        <>
          <h2 style={{ fontSize: 20, fontWeight: 600, marginBottom: 16, color: 'var(--text-primary)' }}>
            <Gift size={20} style={{ marginRight: 8, verticalAlign: 'middle' }} />
            挑战任务
          </h2>
          <div className="tasks-grid">
            {allTasks.map((task) => {
              const progress = task.progress || 0
              const target = task.target_count || 1
              const pct = Math.min(100, Math.round((progress / target) * 100))
              return (
                <div key={task.id} className={`task-card ${task.completed ? 'completed' : ''}`}>
                  <div className="task-icon">{task.icon || '📋'}</div>
                  <div className="task-name">{task.name}</div>
                  <div className="task-desc">{task.description}</div>
                  <div className="task-progress-bar">
                    <div
                      className={`task-progress-fill ${pct >= 100 ? 'done' : ''}`}
                      style={{ width: `${pct}%` }}
                    />
                  </div>
                  <div style={{ fontSize: 12, color: 'var(--text-secondary)', marginBottom: 8 }}>
                    {progress}/{target}
                  </div>
                  <div className="task-reward">
                    {task.reward_points > 0 && <span>🎯 {task.reward_points}积分</span>}
                    {task.reward_coins > 0 && <span><Coins size={12} /> {task.reward_coins}金币</span>}
                  </div>
                  <button
                    className={`claim-btn ${task.reward_claimed ? 'claimed' : ''}`}
                    disabled={!task.completed || task.reward_claimed}
                    onClick={() => handleClaim(task.id)}
                  >
                    {task.reward_claimed ? '已领取' : task.completed ? '领取奖励' : `还需 ${target - progress} 次`}
                  </button>
                </div>
              )
            })}
          </div>
        </>
      )}

      {/* Points + Leaderboard */}
      <div className="points-section">
        <div className="points-card">
          <h3><Coins size={16} style={{ marginRight: 6, verticalAlign: 'middle' }} />我的积分</h3>
          <div className="points-balance">{points?.balance || 0}</div>
          <div style={{ fontSize: 13, color: 'var(--text-secondary)', marginTop: 4 }}>
            累计获得 {points?.total_earned || 0} · 等级 <LevelBadge level={points?.level || 1} />
          </div>
          <div style={{ fontSize: 12, color: 'var(--text-secondary)', marginTop: 12, marginBottom: 4 }}>
            兑换：100积分 = 10金币
          </div>
          <div className="redeem-section">
            <input
              type="number"
              className="redeem-input"
              placeholder="金币数量"
              value={redeemAmount}
              onChange={(e) => setRedeemAmount(e.target.value)}
            />
            <button className="redeem-btn" onClick={handleRedeem} disabled={!redeemAmount}>
              兑换
            </button>
          </div>
        </div>

        <div className="points-card">
          <h3><Trophy size={16} style={{ marginRight: 6, verticalAlign: 'middle' }} />排行榜</h3>
          {leaderboard.length > 0 ? (
            <table className="leaderboard-table">
              <thead>
                <tr><th>#</th><th>用户</th><th>积分</th><th>等级</th></tr>
              </thead>
              <tbody>
                {leaderboard.slice(0, 10).map((entry, i) => (
                  <tr key={entry.user_id}>
                    <td className="leaderboard-rank">{i + 1}</td>
                    <td>{entry.nickname || '用户'}</td>
                    <td>{entry.total_earned}</td>
                    <td><LevelBadge level={entry.level || 1} /></td>
                  </tr>
                ))}
              </tbody>
            </table>
          ) : (
            <div style={{ color: 'var(--text-secondary)', fontSize: 14 }}>暂无排行数据</div>
          )}
        </div>
      </div>
    </div>
  )
}
