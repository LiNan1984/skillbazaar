import { useState, useEffect, useCallback } from 'react'
import { useNavigate, useLocation } from 'react-router-dom'
import { Search, Wallet, Plus, Library, LogIn, UserPlus, LogOut, Store, Target, Shield, Trophy, Box, Globe } from 'lucide-react'
import { getUser, getMe } from '../services/api'
import { useLang, ZH, EN } from '../i18n'

export default function Navbar({ userId, setUserId, authToken, onLoginClick, onRegisterClick, onWalletClick, onLogout }) {
  const navigate = useNavigate()
  const location = useLocation()
  const [searchText, setSearchText] = useState('')
  const [balance, setBalance] = useState(0)
  const [searchTimeout, setSearchTimeout] = useState(null)
  const { t, lang, setLang } = useLang()

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

  const toggleLang = () => {
    setLang(lang === ZH ? EN : ZH)
  }

  return (
    <nav className="navbar">
      <div className="navbar-inner">
        <div className="navbar-logo" onClick={() => navigate('/')}>
          <div className="logo-icon"><img src="/logo.png" alt="logo" style={{ width: 38, height: 38, borderRadius: 8, objectFit: 'cover' }} /></div>
          <div className="logo-text">
            <span>Skill</span>Bazaar
          </div>
        </div>

        <div className="navbar-search">
          <Search size={18} className="search-icon" />
          <input
            type="text"
            placeholder={t('nav.search')}
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

          <button className={`btn btn-sm ${location.pathname === '/publish' ? 'btn-active' : 'btn-primary'}`} onClick={() => navigate('/publish')}>
            <Plus size={16} />
            <span className="btn-text">{t('nav.publish')}</span>
          </button>

          <button className={`btn btn-ghost btn-sm ${location.pathname === '/bounties' ? 'nav-active' : ''}`} onClick={() => navigate('/bounties')}>
            <Target size={16} />
            <span className="btn-text">{t('nav.bounties')}</span>
          </button>

          <button className={`btn btn-ghost btn-sm ${location.pathname === '/activities' ? 'nav-active' : ''}`} onClick={() => navigate('/activities')}>
            <Trophy size={16} />
            <span className="btn-text">{t('nav.activities')}</span>
          </button>

          <button className={`btn btn-ghost btn-sm ${location.pathname === '/sandbox' ? 'nav-active' : ''}`} onClick={() => navigate('/sandbox')} title="Sandbox">
            <Box size={16} />
            <span className="btn-text">{t('nav.sandbox')}</span>
          </button>

          {authToken && (
            <button className={`btn btn-ghost btn-sm ${location.pathname === '/seller' ? 'nav-active' : ''}`} onClick={() => navigate('/seller')}>
              <Store size={16} />
              <span className="btn-text">{t('nav.seller')}</span>
            </button>
          )}

          {authToken && (localStorage.getItem('skillbazaar_role') === 'admin' || localStorage.getItem('skillbazaar_nickname') === 'admin') && (
            <button className={`btn btn-ghost btn-sm ${location.pathname === '/admin' ? 'nav-active' : ''}`} onClick={() => navigate('/admin')}>
              <Shield size={16} />
              <span className="btn-text">{t('nav.admin')}</span>
            </button>
          )}

          <button className={`btn btn-ghost btn-sm ${location.pathname === '/library' ? 'nav-active' : ''}`} onClick={() => navigate('/library')}>
            <Library size={16} />
            <span className="btn-text">{t('nav.library')}</span>
          </button>

          {/* Language Switch */}
          <button className="btn btn-ghost btn-sm lang-switch-btn" onClick={toggleLang} title={lang === ZH ? 'Switch to English' : '切换中文'}>
            <Globe size={16} />
            <span className="btn-text">{lang === ZH ? 'EN' : '中'}</span>
          </button>

          {!authToken ? (
            <>
              <button className="btn btn-ghost btn-sm" onClick={onLoginClick}>
                <LogIn size={16} />
                <span className="btn-text">{t('nav.login')}</span>
              </button>
              <button className="btn btn-primary btn-sm" onClick={onRegisterClick}>
                <UserPlus size={16} />
                <span className="btn-text">{t('nav.register')}</span>
              </button>
            </>
          ) : (
            <>
              <button className="btn btn-ghost btn-sm" onClick={onWalletClick}>
                <Wallet size={16} />
                <span className="btn-text">{t('nav.wallet')}</span>
              </button>
              <span className="navbar-username">
                {localStorage.getItem('skillbazaar_nickname') || localStorage.getItem('skillbazaar_username') || t('nav.user')}
              </span>
              <button className="btn btn-ghost btn-sm" onClick={onLogout}>
                <LogOut size={16} />
                <span className="btn-text">{t('nav.logout')}</span>
              </button>
            </>
          )}
        </div>
      </div>
    </nav>
  )
}
