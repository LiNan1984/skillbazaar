import { useState, useEffect, useRef, useCallback } from 'react'
import { Bell } from 'lucide-react'
import { getNotifications, markNotificationRead } from '../services/api'

const POLL_INTERVAL_MS = 60000
const MAX_ITEMS = 10

const TYPE_ICONS = {
  product_bought: '🛒',
  product_sold: '💰',
  bounty_application: '📝',
  bounty_selected: '🎉',
  bounty_delivered: '📦',
  bounty_accepted: '✅',
  bounty_rejected: '❌',
  cron_result: '⏰',
}

function relativeTime(iso) {
  if (!iso) return ''
  const then = new Date(iso.includes('T') ? iso : iso.replace(' ', 'T'))
  const diffSec = Math.max(0, Math.floor((Date.now() - then.getTime()) / 1000))
  if (diffSec < 60) return '刚刚'
  if (diffSec < 3600) return `${Math.floor(diffSec / 60)} 分钟前`
  if (diffSec < 86400) return `${Math.floor(diffSec / 3600)} 小时前`
  if (diffSec < 86400 * 30) return `${Math.floor(diffSec / 86400)} 天前`
  return then.toLocaleDateString()
}

export default function NotificationBell({ token }) {
  const [open, setOpen] = useState(false)
  const [notifications, setNotifications] = useState([])
  const [unreadCount, setUnreadCount] = useState(0)
  const dropdownRef = useRef(null)

  const fetchNotifications = useCallback(async () => {
    if (!token) return
    try {
      const data = await getNotifications(false, token)
      const items = (data.notifications || []).slice(0, MAX_ITEMS)
      setNotifications(items)
      setUnreadCount(data.unread_count ?? 0)
    } catch {
      // 401 / network errors stay silent; keep last known state
    }
  }, [token])

  useEffect(() => {
    if (!token) {
      setNotifications([])
      setUnreadCount(0)
      setOpen(false)
      return
    }
    fetchNotifications()
    const timer = setInterval(fetchNotifications, POLL_INTERVAL_MS)
    return () => clearInterval(timer)
  }, [token, fetchNotifications])

  useEffect(() => {
    if (!open) return undefined
    const onClickOutside = (e) => {
      if (dropdownRef.current && !dropdownRef.current.contains(e.target)) {
        setOpen(false)
      }
    }
    document.addEventListener('mousedown', onClickOutside)
    return () => document.removeEventListener('mousedown', onClickOutside)
  }, [open])

  if (!token) return null

  const handleToggle = () => {
    setOpen((prev) => !prev)
    if (!open) fetchNotifications()
  }

  const handleItemClick = async (item) => {
    if (item.is_read) return
    // optimistic update; next 60s poll cannot bounce it back since the server state changed
    setNotifications((prev) => prev.map((n) => (n.id === item.id ? { ...n, is_read: 1 } : n)))
    setUnreadCount((prev) => Math.max(0, prev - 1))
    try {
      await markNotificationRead(item.id, token)
    } catch {
      // revert on failure so badge stays truthful
      setNotifications((prev) => prev.map((n) => (n.id === item.id ? { ...n, is_read: 0 } : n)))
      setUnreadCount((prev) => prev + 1)
    }
  }

  return (
    <div className="notif-bell-wrapper" ref={dropdownRef}>
      <button
        className="btn btn-ghost btn-sm notif-bell-btn"
        onClick={handleToggle}
        title="通知"
        aria-label="通知"
      >
        <Bell size={16} />
        {unreadCount > 0 && (
          <span className="notif-badge">
            {unreadCount > 99 ? '99+' : unreadCount}
          </span>
        )}
      </button>

      {open && (
        <div className="notif-dropdown">
          <div className="notif-dropdown-header">
            <span>站内通知</span>
            {unreadCount > 0 && <span className="notif-unread-tag">{unreadCount} 条未读</span>}
          </div>
          <div className="notif-dropdown-list">
            {notifications.length === 0 ? (
              <div className="notif-empty">暂无通知</div>
            ) : (
              notifications.map((item) => (
                <button
                  key={item.id}
                  className={`notif-item ${item.is_read ? 'is-read' : ''}`}
                  onClick={() => handleItemClick(item)}
                >
                  <span className="notif-item-icon">
                    {TYPE_ICONS[item.type] || '🔔'}
                  </span>
                  <span className="notif-item-body">
                    <span className="notif-item-title">{item.title}</span>
                    <span className="notif-item-content">{item.content}</span>
                    <span className="notif-item-time">{relativeTime(item.created_at)}</span>
                  </span>
                  {!item.is_read && <span className="notif-item-dot" />}
                </button>
              ))
            )}
          </div>
        </div>
      )}
    </div>
  )
}
