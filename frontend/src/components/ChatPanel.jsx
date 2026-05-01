import { useState, useRef, useEffect } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { X, Send } from 'lucide-react'
import { sendChat } from '../services/api'

const QUICK_REPLIES = [
  { label: '🤖 Agent', value: '我想看看 Agent 类的商品' },
  { label: '⚡ Skill', value: '有没有好用的 Skill 推荐？' },
  { label: '⏰ Cron', value: '推荐一些 Cron 定时任务工具' },
  { label: '🔄 Workflow', value: '有哪些 Workflow 自动化工具？' },
  { label: '🔥 热门', value: '最近有什么热门商品？' },
  { label: '💰 便宜', value: '有没有便宜好用的商品？' },
]

const SLOT_LABELS = {
  category: '品类',
  keyword: '关键词',
  minPrice: '最低价',
  maxPrice: '最高价',
}

export default function ChatPanel({ open, onClose, userId }) {
  const [messages, setMessages] = useState([])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const [slots, setSlots] = useState({
    category: null,
    keyword: null,
    minPrice: null,
    maxPrice: null,
  })
  const messagesEndRef = useRef(null)
  const inputRef = useRef(null)

  useEffect(() => {
    if (open && messages.length === 0) {
      setMessages([
        {
          role: 'bot',
          content:
            '您好！我是 BS买卖助手，帮您搜索推荐 AI 技能商品，也能引导您上传发布。有什么需要？',
        },
      ])
    }
  }, [open, messages.length])

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  useEffect(() => {
    if (open) {
      setTimeout(() => inputRef.current?.focus(), 300)
    }
  }, [open])

  const handleSend = async (text) => {
    const message = text || input.trim()
    if (!message || loading) return

    setInput('')
    setMessages((prev) => [...prev, { role: 'user', content: message }])
    setLoading(true)

    try {
      const data = await sendChat(userId, message)
      const reply = data.reply || data.message || data.response || ''
      const products = data.products || data.recommendations || []

      if (reply) {
        setMessages((prev) => [...prev, { role: 'bot', content: reply }])
      }

      if (products.length > 0) {
        const tableRows = products
          .map(
            (p) =>
              `| [${p.name}](/product/${p.id}) | ${p.category || ''} | **¥${p.price || 0}** | ${p.rating || 'N/A'} |`
          )
          .join('\n')
        const table = `### 推荐商品\n\n| 名称 | 分类 | 价格 | 评分 |\n|------|------|------|------|\n${tableRows}`
        setMessages((prev) => [...prev, { role: 'bot', content: table }])
      }

      if (!reply && products.length === 0) {
        setMessages((prev) => [...prev, { role: 'bot', content: '抱歉，我暂时无法理解，请换个方式描述您的需求。' }])
      }
    } catch {
      setMessages((prev) => [
        ...prev,
        { role: 'bot', content: '网络异常，请稍后重试。' },
      ])
    } finally {
      setLoading(false)
    }
  }

  const handleKeyDown = (e) => {
    if (e.key === 'Enter') {
      e.preventDefault()
    }
  }

  const filledSlotsCount = Object.values(slots).filter((v) => v !== null).length

  return (
    <div className={`chat-panel ${open ? 'open' : ''}`}>
      <div className="chat-header">
        <div className="chat-header-left">
          <div className="chat-header-avatar">🤖</div>
          <div className="chat-header-info">
            <span className="chat-header-name">BS买卖助手</span>
            <span className="chat-header-status">
              <span className="chat-header-status-dot" />
              在线
            </span>
          </div>
        </div>
        <button className="chat-close-btn" onClick={onClose}>
          <X size={20} />
        </button>
      </div>

      {filledSlotsCount > 0 && (
        <div className="slot-status">
          <span className="slot-label">筛选条件</span>
          {Object.entries(slots).map(([key, value]) => (
            <span key={key} className={`slot-chip ${value ? 'filled' : ''}`}>
              {value ? '✓' : '○'} {SLOT_LABELS[key]}
              {value ? `: ${value}` : ''}
            </span>
          ))}
        </div>
      )}

      <div className="chat-messages">
        {messages.map((msg, i) => (
          <div key={i} className={`chat-message ${msg.role}`}>
            {msg.role === 'bot' && <div className="message-avatar">🤖</div>}
            <div className={`message-bubble ${msg.role}`}>
              <ReactMarkdown remarkPlugins={[remarkGfm]}>{msg.content}</ReactMarkdown>
            </div>
            {msg.role === 'user' && <div className="message-avatar">😊</div>}
          </div>
        ))}
        {loading && (
          <div className="chat-message bot">
            <div className="message-avatar">🤖</div>
            <div className="message-bubble bot typing">
              <span className="typing-dot">●</span>
              <span className="typing-dot">●</span>
              <span className="typing-dot">●</span>
            </div>
          </div>
        )}
        <div ref={messagesEndRef} />
      </div>

      {messages.length <= 1 && (
        <div className="quick-replies">
          {QUICK_REPLIES.map((qr) => (
            <button
              key={qr.label}
              className="quick-reply-btn"
              onClick={() => handleSend(qr.value)}
            >
              {qr.label}
            </button>
          ))}
        </div>
      )}

      <div className="chat-input-area">
        <input
          ref={inputRef}
          type="text"
          className="chat-input"
          placeholder="输入您的问题..."
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          disabled={loading}
        />
        <button
          className="chat-send-btn"
          onClick={() => handleSend()}
          disabled={loading || !input.trim()}
        >
          <Send size={18} />
        </button>
      </div>

      <div className="chat-footer">回复内容由 AI 助手生成，仅供参考</div>
    </div>
  )
}
