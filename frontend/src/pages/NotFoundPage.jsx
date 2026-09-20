import { Link } from 'react-router-dom'
import { Home, Search } from 'lucide-react'

export default function NotFoundPage() {
  return (
    <div className="page-shell" style={{ minHeight: '60vh', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
      <div style={{ textAlign: 'center', maxWidth: 420 }}>
        <div style={{ fontSize: 72, fontWeight: 800, color: 'var(--accent-primary)', lineHeight: 1 }}>404</div>
        <h1 style={{ fontSize: 22, margin: '16px 0 8px', color: 'var(--text-primary)' }}>页面不存在</h1>
        <p style={{ color: 'var(--text-secondary)', marginBottom: 24 }}>
          你访问的页面可能已被移除、名称更改或暂时不可用。
        </p>
        <div style={{ display: 'flex', gap: 12, justifyContent: 'center' }}>
          <Link to="/" className="btn btn-primary">
            <Home size={16} /> 返回首页
          </Link>
          <Link to="/bounties" className="btn btn-secondary">
            <Search size={16} /> 浏览悬赏
          </Link>
        </div>
      </div>
    </div>
  )
}
