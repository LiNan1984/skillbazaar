import { useState, useEffect, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import { Search, Wallet, Plus, Library, LogIn, UserPlus, LogOut, Store, Target } from 'lucide-react'
import { getUser, getMe } from '../services/api'

export default function Navbar({ userId, setUserId, authToken, onLoginClick, onRegisterClick, onWalletClick, onLogout }) {
  const navigate = useNavigate()
  const [searchText, setSearchText] = useState('')
  const [balance, setBalance] = useState(0)
  const [searchTimeout, setSearchTimeout] = useState(null)

  useEffect(() => {
    if (authToken) {
      getMe(authToken)
        .then((data) => setBalance(data.coins ?? 0))
        .catch(() => {})
    } else if (userId) {
      getUser(userId)
        .then((data) => setBalance(data.balance ?? data.coins ?? 0))
        .catch(() => {})
    }
  }, [userId, authToken])

  const handleSearch = useCallback(
    (value) => {
      setSearchText(value)
      if (searchTimeout) clearTimeout(searchTimeout)
      const timeout = setTimeout(() => {
        const params = new URLSearchParams(window.location.search)
        if (value) {
          params.set('keyword', value)
        } else {
          params.delete('keyword')
        }
        navigate(`/?${params.toString()}`)
      }, 400)
      setSearchTimeout(timeout)
    },
    [searchTimeout, navigate]
  )

  return (
    <nav className="navbar">
      <div className="navbar-inner">
        <div className="navbar-logo" onClick={() => navigate('/')}>
          <div className="logo-icon">🏪</div>
          <div className="logo-text">
            <span>Skill</span>Bazaar
          </div>
        </div>

        <div className="navbar-search">
          <Search size={18} className="search-icon" />
          <input
            type="text"
            placeholder="搜索 Agent、Skill、Cron..."
            value={searchText}
            onChange={(e) => handleSearch(e.target.value)}
            className="search-input"
          />
        </div>

        <div className="navbar-actions">
          <div className="wallet-display" onClick={authToken ? onWalletClick : undefined} style={authToken ? { cursor: 'pointer' } : {}}>
            <Wallet size={16} />
            <span className="wallet-coin">💰</span>
            <span className="wallet-amount">{balance.toLocaleString()}</span>
          </div>

          <button className="btn btn-primary btn-sm" onClick={() => navigate('/publish')}>
            <Plus size={16} />
            <span className="btn-text">发布商品</span>
          </button>

          <button className="btn btn-ghost btn-sm" onClick={() => navigate('/bounties')}>
            <Target size={16} />
            <span className="btn-text">悬赏市场</span>
          </button>

          {authToken && (
            <button className="btn btn-ghost btn-sm" onClick={() => navigate('/seller')}>
              <Store size={16} />
              <span className="btn-text">卖家中心</span>
            </button>
          )}

          <button className="btn btn-ghost btn-sm" onClick={() => navigate('/library')}>
            <Library size={16} />
            <span className="btn-text">我的库</span>
          </button>

          {!authToken ? (
            <>
              <button className="btn btn-ghost btn-sm" onClick={onLoginClick}>
                <LogIn size={16} />
                <span className="btn-text">登录</span>
              </button>
              <button className="btn btn-primary btn-sm" onClick={onRegisterClick}>
                <UserPlus size={16} />
                <span className="btn-text">注册</span>
              </button>
            </>
          ) : (
            <>
              <button className="btn btn-ghost btn-sm" onClick={onWalletClick}>
                <Wallet size={16} />
                <span className="btn-text">钱包</span>
              </button>
              <span className="navbar-username">
                {localStorage.getItem('skillbazaar_nickname') || localStorage.getItem('skillbazaar_username') || '用户'}
              </span>
              <button className="btn btn-ghost btn-sm" onClick={onLogout}>
                <LogOut size={16} />
                <span className="btn-text">退出</span>
              </button>
            </>
          )}
        </div>
      </div>
    </nav>
  )
}
