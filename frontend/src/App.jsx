import { Routes, Route } from 'react-router-dom'
import { useState, useEffect, lazy, Suspense } from 'react'
import Navbar from './components/Navbar'
import FloatingAssistant from './components/FloatingAssistant'
import HomePage from './pages/HomePage'
import AuthModal from './components/AuthModal'
import WalletPanel from './components/WalletPanel'
import { initUser } from './services/api'

const ProductDetailPage = lazy(() => import('./pages/ProductDetailPage'))
const PublishPage = lazy(() => import('./pages/PublishPage'))
const MyLibraryPage = lazy(() => import('./pages/MyLibraryPage'))
const ChatPanel = lazy(() => import('./components/ChatPanel'))
const SellerDashboard = lazy(() => import('./pages/SellerDashboard'))
const BountyPage = lazy(() => import('./pages/BountyPage'))
const BountyDetailPage = lazy(() => import('./pages/BountyDetailPage'))

function App() {
  const [userId, setUserId] = useState(() => localStorage.getItem('skillbazaar_user_id') || '')
  const [chatOpen, setChatOpen] = useState(false)
  const [authModal, setAuthModal] = useState(null) // null | 'login' | 'register'
  const [walletOpen, setWalletOpen] = useState(false)
  const [authToken, setAuthToken] = useState(() => localStorage.getItem('skillbazaar_token') || '')

  const handleAuthSuccess = (data) => {
    setUserId(data.user_id)
    setAuthToken(data.token)
    setAuthModal(null)
  }

  useEffect(() => {
    if (!userId) {
      initUser()
        .then((data) => {
          const id = data.user_id || data.id || data.userId
          if (id) {
            localStorage.setItem('skillbazaar_user_id', id)
            setUserId(id)
          }
        })
        .catch(() => {})
    }
  }, [userId])

  return (
    <div className="app">
      <Navbar
        userId={userId}
        setUserId={setUserId}
        authToken={authToken}
        onLoginClick={() => setAuthModal('login')}
        onRegisterClick={() => setAuthModal('register')}
        onWalletClick={() => setWalletOpen(true)}
        onLogout={() => {
          localStorage.removeItem('skillbazaar_token')
          localStorage.removeItem('skillbazaar_user_id')
          localStorage.removeItem('skillbazaar_username')
          localStorage.removeItem('skillbazaar_nickname')
          setUserId('')
          setAuthToken('')
        }}
      />
      <main className="main-content">
        <Suspense fallback={null}>
          <Routes>
            <Route path="/" element={<HomePage userId={userId} />} />
            <Route path="/product/:id" element={<ProductDetailPage userId={userId} />} />
            <Route path="/publish" element={<PublishPage userId={userId} authToken={authToken} />} />
            <Route path="/library" element={<MyLibraryPage userId={userId} />} />
            <Route path="/seller" element={<SellerDashboard userId={userId} authToken={authToken} />} />
            <Route path="/bounties" element={<BountyPage userId={userId} authToken={authToken} />} />
            <Route path="/bounty/:id" element={<BountyDetailPage userId={userId} authToken={authToken} />} />
          </Routes>
        </Suspense>
      </main>
      <FloatingAssistant isOpen={chatOpen} onClick={() => setChatOpen(!chatOpen)} />
      {chatOpen && (
        <Suspense fallback={null}>
          <ChatPanel open={chatOpen} onClose={() => setChatOpen(false)} userId={userId} />
        </Suspense>
      )}
      {authModal && (
        <AuthModal mode={authModal} onClose={() => setAuthModal(null)} onSuccess={handleAuthSuccess} />
      )}
      {walletOpen && (
        <WalletPanel onClose={() => setWalletOpen(false)} token={authToken} coins={0} />
      )}
    </div>
  )
}

export default App
