import { useState, useRef, useEffect } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { X, Send, RotateCcw } from 'lucide-react'
import { sendChat } from '../services/api'
import WelcomeCard from './cards/WelcomeCard'
import PublishCard from './cards/PublishCard'
import BountyCard from './cards/BountyCard'
import AnalysisCard from './cards/AnalysisCard'

const STORAGE_KEY_MSGS = 'skillbazaar_chat_messages'
const STORAGE_KEY_CARD = 'skillbazaar_active_card'

function getStoredCard() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY_CARD)
    return raw ? JSON.parse(raw) : null
  } catch {
    return null
  }
}

function saveCard(card) {
  if (card) {
    localStorage.setItem(STORAGE_KEY_CARD, JSON.stringify(card))
  } else {
    localStorage.removeItem(STORAGE_KEY_CARD)
  }
}

function getStoredMessages() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY_MSGS)
    if (raw) {
      const msgs = JSON.parse(raw)
      if (Array.isArray(msgs) && msgs.length > 0) return msgs
    }
  } catch { /* ignore */ }
  return null
}

function saveMessages(messages) {
  try {
    localStorage.setItem(STORAGE_KEY_MSGS, JSON.stringify(messages.slice(-100)))
  } catch { /* ignore */ }
}

function renderCard(card, props) {
  if (!card) return null
  switch (card.type) {
    case 'publish':
      return <PublishCard card={card} {...props} />
    case 'bounty':
      return <BountyCard card={card} {...props} />
    case 'analysis':
      return <AnalysisCard card={card} />
    default:
      return null
  }
}

export default function ChatPanel({ open, onClose, userId, authToken }) {
  const [messages, setMessages] = useState(() => {
    const stored = getStoredMessages()
    if (stored) return stored
    return [
      {
        role: 'bot',
        content: '您好！我是 BS买卖助手，帮您搜索推荐 AI 技能商品，也能引导您上传发布。有什么需要？',
        welcome: true,
      },
    ]
  })
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const [activeCard, setActiveCard] = useState(getStoredCard)
  const messagesEndRef = useRef(null)
  const inputRef = useRef(null)

  // Persist messages whenever they change
  useEffect(() => {
    saveMessages(messages)
  }, [messages])

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, activeCard])

  useEffect(() => {
    if (open) {
      setTimeout(() => inputRef.current?.focus(), 300)
    }
  }, [open])

  const handleCardUpdate = (updatedCard) => {
    setActiveCard(updatedCard)
    saveCard(updatedCard)
  }

  const handleCardSubmit = (productId) => {
    setActiveCard(null)
    saveCard(null)
    setMessages((prev) => [
      ...prev,
      { role: 'bot', content: `商品已成功发布！[查看商品](/product/${productId})` },
    ])
  }

  const handleBountySubmit = (bountyId) => {
    setActiveCard(null)
    saveCard(null)
    setMessages((prev) => [
      ...prev,
      { role: 'bot', content: `悬赏已成功发布！[查看悬赏](/bounty/${bountyId})` },
    ])
  }

  const handleCardCancel = () => {
    setActiveCard(null)
    saveCard(null)
  }

  const handleSend = async (text) => {
    const message = text || input.trim()
    if (!message || loading) return

    setInput('')
    setMessages((prev) => [...prev, { role: 'user', content: message }])

    // Show thinking message immediately
    const thinkingText = message.includes('搜索') || message.includes('找') || message.includes('推荐')
      ? '正在搜索相关商品...'
      : message.includes('分析') || message.includes('趋势')
      ? '正在分析市场数据...'
      : message.includes('发布') || message.includes('上传') || message.includes('上架')
      ? '正在准备发布表单...'
      : message.includes('悬赏') || message.includes('找人')
      ? '正在创建悬赏任务...'
      : '正在思考您的需求...'

    const thinkingId = Date.now()
    setMessages((prev) => [...prev, { id: thinkingId, role: 'bot', content: thinkingText, thinking: true }])
    setLoading(true)

    try {
      const data = await sendChat(userId, message, activeCard)
      const reply = data.reply || data.message || data.response || ''
      const card = data.card || null
      const products = data.products || data.recommendations || []

      // Remove thinking message and add real response
      setMessages((prev) => {
        const withoutThinking = prev.filter((m) => m.id !== thinkingId)
        const updated = [...withoutThinking]
        if (reply) {
          updated.push({ role: 'bot', content: reply })
        }
        if (products.length > 0) {
          const tableRows = products
            .map(
              (p) =>
                `| [${p.name}](/product/${p.id}) | ${p.category || ''} | **¥${p.price || 0}** | ${p.rating || 'N/A'} |`
            )
            .join('\n')
          const table = `### 推荐商品\n\n| 名称 | 分类 | 价格 | 评分 |\n|------|------|------|------|\n${tableRows}`
          updated.push({ role: 'bot', content: table })
        }
        if (!reply && products.length === 0 && !card) {
          updated.push({ role: 'bot', content: '抱歉，我暂时无法理解，请换个方式描述您的需求。' })
        }
        return updated
      })

      if (card) {
        setActiveCard(card)
        saveCard(card)
      }
    } catch {
      setMessages((prev) => {
        const withoutThinking = prev.filter((m) => m.id !== thinkingId)
        return [...withoutThinking, { role: 'bot', content: '网络异常，请稍后重试。' }]
      })
    } finally {
      setLoading(false)
    }
  }

  const handleKeyDown = (e) => {
    if (e.key === 'Enter') {
      e.preventDefault()
    }
  }

  const cardProps = {
    authToken,
    userId,
    onUpdate: handleCardUpdate,
    onSubmit: activeCard?.type === 'bounty' ? handleBountySubmit : handleCardSubmit,
    onCancel: handleCardCancel,
  }

  return (
    <div className={`chat-panel ${open ? 'open' : ''}`}>
      <div className="chat-header">
        <div className="chat-header-left">
          <div className="chat-header-avatar"><img src="/logo.png" alt="BS" style={{ width: 28, height: 28, borderRadius: 6 }} /></div>
          <div className="chat-header-info">
            <span className="chat-header-name">BS买卖助手</span>
            <span className="chat-header-status">
              <span className="chat-header-status-dot" />
              在线
            </span>
          </div>
        </div>
        <button className="chat-header-btn" onClick={() => {
          setMessages([
            {
              role: 'bot',
              content: '您好！我是 BS买卖助手，帮您搜索推荐 AI 技能商品，也能引导您上传发布。有什么需要？',
              welcome: true,
            },
          ])
          setActiveCard(null)
          saveCard(null)
          localStorage.removeItem(STORAGE_KEY_MSGS)
        }} title="清除会话">
          <RotateCcw size={16} />
        </button>
        <button className="chat-close-btn" onClick={onClose}>
          <X size={20} />
        </button>
      </div>

      <div className="chat-messages">
        {messages.map((msg, i) => (
          <div key={msg.id || i} className={`chat-message ${msg.role}`}>
            {msg.role === 'bot' && <div className="message-avatar"><img src="/logo.png" alt="BS" style={{ width: 24, height: 24, borderRadius: 6 }} /></div>}
            <div className={`message-bubble ${msg.role} ${msg.thinking ? 'thinking' : ''}`}>
              {msg.thinking ? (
                <span>{msg.content}</span>
              ) : (
                <ReactMarkdown remarkPlugins={[remarkGfm]}>{msg.content}</ReactMarkdown>
              )}
              {msg.welcome && (
                <WelcomeCard onAction={(value) => handleSend(value)} />
              )}
            </div>
            {msg.role === 'user' && <div className="message-avatar">😊</div>}
          </div>
        ))}
        {activeCard && (
          <div className="chat-message bot">
            <div className="message-avatar"><img src="/logo.png" alt="BS" style={{ width: 24, height: 24, borderRadius: 6 }} /></div>
            <div className="message-bubble bot">
              {renderCard(activeCard, { card: activeCard, ...cardProps })}
            </div>
          </div>
        )}
        {loading && (
          <div className="chat-message bot">
            <div className="message-avatar"><img src="/logo.png" alt="BS" style={{ width: 24, height: 24, borderRadius: 6 }} /></div>
            <div className="message-bubble bot typing">
              <span className="typing-dot">●</span>
              <span className="typing-dot">●</span>
              <span className="typing-dot">●</span>
            </div>
          </div>
        )}
        <div ref={messagesEndRef} />
      </div>

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
