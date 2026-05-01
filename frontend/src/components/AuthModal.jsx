import { useState } from 'react'
import { X, User, Lock, Mail } from 'lucide-react'
import { register, login } from '../services/api'

export default function AuthModal({ mode: initialMode, onClose, onSuccess }) {
  const [mode, setMode] = useState(initialMode || 'login')
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [nickname, setNickname] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  const handleSubmit = async (e) => {
    e.preventDefault()
    setError('')
    setLoading(true)

    try {
      if (mode === 'register') {
        const data = await register(username, password, nickname || undefined)
        if (data.user_id) {
          setMode('login')
          setError('')
        } else {
          setError(data.detail || '注册失败')
        }
      } else {
        const data = await login(username, password)
        if (data.token) {
          localStorage.setItem('skillbazaar_token', data.token)
          localStorage.setItem('skillbazaar_user_id', data.user_id)
          localStorage.setItem('skillbazaar_username', data.username)
          localStorage.setItem('skillbazaar_nickname', data.nickname)
          onSuccess(data)
        } else {
          setError('用户名或密码错误')
        }
      }
    } catch (err) {
      setError(err?.detail || err?.message || '操作失败')
    } finally {
      setLoading(false)
    }
  }

  const switchMode = () => {
    setMode(mode === 'login' ? 'register' : 'login')
    setError('')
  }

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="auth-modal" onClick={(e) => e.stopPropagation()}>
        <button className="modal-close" onClick={onClose}><X size={20} /></button>

        <div className="auth-modal-header">
          <h2>{mode === 'login' ? '登录' : '注册'}</h2>
          <p>{mode === 'login' ? '登录你的 SkillBazaar 账户' : '创建新账户，开始交易'}</p>
        </div>

        <form className="auth-form" onSubmit={handleSubmit}>
          {error && <div className="form-error">{error}</div>}

          <div className="form-group">
            <label className="form-label"><User size={14} /> 用户名</label>
            <input
              type="text"
              className="form-input"
              placeholder="输入用户名"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              required
              minLength={3}
            />
          </div>

          {mode === 'register' && (
            <div className="form-group">
              <label className="form-label">昵称</label>
              <input
                type="text"
                className="form-input"
                placeholder="显示名称（可选）"
                value={nickname}
                onChange={(e) => setNickname(e.target.value)}
              />
            </div>
          )}

          <div className="form-group">
            <label className="form-label"><Lock size={14} /> 密码</label>
            <input
              type="password"
              className="form-input"
              placeholder="输入密码"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
              minLength={6}
            />
          </div>

          <button type="submit" className="btn btn-primary btn-auth" disabled={loading}>
            {loading ? '处理中...' : mode === 'login' ? '登录' : '注册'}
          </button>

          <div className="auth-switch">
            {mode === 'login' ? (
              <span>没有账户？<button type="button" onClick={switchMode}>注册</button></span>
            ) : (
              <span>已有账户？<button type="button" onClick={switchMode}>登录</button></span>
            )}
          </div>
        </form>
      </div>
    </div>
  )
}
