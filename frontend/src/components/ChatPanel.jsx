import { useState, useRef, useEffect, useMemo } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { X, Send, RotateCcw, FileText } from 'lucide-react'
import { sendChat, getChatHistory, clearChatHistory } from '../services/api'
import WelcomeCard from './cards/WelcomeCard'
import PublishCard from './cards/PublishCard'
import BountyCard from './cards/BountyCard'
import AnalysisCard from './cards/AnalysisCard'
import MatchCard from './cards/MatchCard'

const WELCOME = {
  role: 'bot',
  content: '您好！我是 BS买卖助手，帮您搜索推荐 AI 技能商品，也能引导您上传发布。有什么需要？',
  welcome: true,
}

// Cards rendered inline inside chat messages (live and replayed history).
const INTERACTIVE_CARD_TYPES = ['publish', 'bounty', 'analysis', 'match']

function isDoneCard(card) {
  return card?.data?.mode === 'done'
}

function ReadOnlyCardSummary({ card }) {
  const isBounty = card.type === 'bounty'
  const form = card.data?.form || card.data || {}
  const title = form.title || form.name || (isBounty ? '历史悬赏需求' : '历史商品草稿')
  const rows = [
    ['描述', form.description],
    ['分类', form.category],
    isBounty
      ? ['预算', form.budget_min || form.budget_max ? `¥${form.budget_min || 0} - ¥${form.budget_max || 0}` : null]
      : ['价格', form.price != null && form.price !== '' ? `¥${form.price}` : null],
    ['截止日期', form.deadline],
  ].filter(([, v]) => v !== null && v !== undefined && v !== '')

  return (
    <div className="publish-card" style={{ opacity: 0.85 }}>
      <div className="publish-card-header" style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
        <FileText size={14} />
        {isBounty ? '历史悬赏（只读）' : '历史发布草稿（只读）'}
      </div>
      <div className="publish-card-preview">
        <div className="publish-card-field">
          <span className="publish-card-label">标题：</span>
          <span>{title}</span>
        </div>
        {rows.map(([label, value]) => (
          <div className="publish-card-field" key={label}>
            <span className="publish-card-label">{label}：</span>
            <span>{value}</span>
          </div>
        ))}
        <div style={{ fontSize: 12, opacity: 0.7, marginTop: 6 }}>
          历史卡片仅供查看，如需再次操作请重新发起需求。
        </div>
      </div>
    </div>
  )
}

function renderCard(card, props) {
  if (!card) return null
  switch (card.type) {
    case 'publish':
      return props.readOnly ? <ReadOnlyCardSummary card={card} /> : <PublishCard card={card} {...props} />
    case 'bounty':
      return props.readOnly ? <ReadOnlyCardSummary card={card} /> : <BountyCard card={card} {...props} />
    case 'analysis':
      return <AnalysisCard card={card} />
    case 'match':
      return <MatchCard card={card} authToken={props.authToken} userId={props.userId} />
    default:
      // Legacy 'products' cards degrade to a non-interactive list (no buttons).
      return null
  }
}

export default function ChatPanel({ open, onClose, userId, authToken }) {
  const [messages, setMessages] = useState([WELCOME])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const [clearing, setClearing] = useState(false)
  const messagesEndRef = useRef(null)
  const inputRef = useRef(null)

  // Load persisted history from server on open
  useEffect(() => {
    if (!authToken) {
      setMessages([WELCOME])
      return
    }
    let cancelled = false
    getChatHistory(authToken, 20)
      .then((data) => {
        if (cancelled) return
        const rows = data.messages || []
        if (rows.length === 0) {
          setMessages([WELCOME])
          return
        }
        setMessages(rows.map((m) => ({
          role: m.role === 'user' ? 'user' : 'bot',
          content: m.content || '',
          card: m.card || null,
        })))
      })
      .catch(() => {
        // 401 or network error: stay on the welcome screen without console noise
        if (!cancelled) setMessages([WELCOME])
      })
    return () => {
      cancelled = true
    }
  }, [authToken])

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  useEffect(() => {
    if (open) {
      setTimeout(() => inputRef.current?.focus(), 300)
    }
  }, [open])

  // Index of the latest editable (fill/preview, not done) form card per type.
  // Only that card stays interactive on replay; older ones render read-only.
  const editableIndexByType = useMemo(() => {
    const map = {}
    messages.forEach((m, i) => {
      const card = m.card
      if (card && card.step === 'fill' && !isDoneCard(card)) {
        map[card.type] = i
      }
    })
    return map
  }, [messages])

  // Card attached to the next outgoing message (slot-update context).
  const activeFormCard = useMemo(() => {
    for (let i = messages.length - 1; i >= 0; i -= 1) {
      const card = messages[i].card
      if (card && card.step === 'fill' && !isDoneCard(card)) {
        return card
      }
    }
    return null
  }, [messages])

  const handleCardUpdate = (index, updatedCard) => {
    setMessages((prev) => prev.map((m, i) => (i === index ? { ...m, card: updatedCard } : m)))
  }

  const handleCardCancel = (index) => {
    setMessages((prev) => prev.map((m, i) => (i === index ? { ...m, card: null } : m)))
  }

  const handleCardSubmit = (productId) => {
    setMessages((prev) => [
      ...prev,
      { role: 'bot', content: `商品已成功发布！[查看商品](/product/${productId})` },
    ])
  }

  const handleBountySubmit = (bountyId) => {
    setMessages((prev) => [
      ...prev,
      { role: 'bot', content: `悬赏已成功发布！[查看悬赏](/bounty/${bountyId})` },
    ])
  }

  const handleSend = async (text) => {
    const message = text || input.trim()
    if (!message || loading) return
    if (!authToken) return

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
      const data = await sendChat(authToken, message, activeFormCard)
      const reply = data.reply || data.message || data.response || ''
      const card = data.card && INTERACTIVE_CARD_TYPES.includes(data.card.type) ? data.card : null

      // Attach the card to the current-turn bot message so it renders live
      // (previously it only appeared after a history refresh).
      setMessages((prev) => {
        const withoutThinking = prev.filter((m) => m.id !== thinkingId)
        const updated = [...withoutThinking]
        if (reply) {
          updated.push({ role: 'bot', content: reply, card })
        } else if (card) {
          updated.push({ role: 'bot', content: '', card })
        } else {
          updated.push({ role: 'bot', content: '抱歉，我暂时无法理解，请换个方式描述您的需求。' })
        }
        return updated
      })
    } catch {
      setMessages((prev) => {
        const withoutThinking = prev.filter((m) => m.id !== thinkingId)
        return [...withoutThinking, { role: 'bot', content: '网络异常，请稍后重试。' }]
      })
    } finally {
      setLoading(false)
    }
  }

  const handleClear = async () => {
    if (clearing) return
    setClearing(true)
    try {
      if (authToken) {
        await clearChatHistory(authToken)
      }
    } catch {
      // even if the request fails, reset local view
    } finally {
      setClearing(false)
    }
    setMessages([WELCOME])
  }

  const handleKeyDown = (e) => {
    // Do not send while an IME composition is in progress (Chinese input).
    if (e.nativeEvent?.isComposing || e.keyCode === 229) return
    if (e.key === 'Enter') {
      e.preventDefault()
      handleSend()
    }
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
        <button className="chat-header-btn" onClick={handleClear} disabled={clearing} title="清空对话">
          <RotateCcw size={16} />
        </button>
        <button className="chat-close-btn" onClick={onClose}>
          <X size={20} />
        </button>
      </div>

      <div className="chat-messages">
        {messages.map((msg, i) => {
          const card = msg.card
          const readOnly = !!card && (card.type === 'publish' || card.type === 'bounty')
            && editableIndexByType[card.type] !== i && card.step === 'fill'
            && !isDoneCard(card)
          const cardProps = {
            authToken,
            userId,
            onUpdate: (updatedCard) => handleCardUpdate(i, updatedCard),
            onSubmit: card?.type === 'bounty' ? handleBountySubmit : handleCardSubmit,
            onCancel: () => handleCardCancel(i),
            readOnly,
          }
          return (
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
                {!msg.welcome && card && INTERACTIVE_CARD_TYPES.includes(card.type) && (
                  <div style={{ marginTop: 10 }}>
                    {renderCard(card, cardProps)}
                  </div>
                )}
              </div>
              {msg.role === 'user' && <div className="message-avatar">😊</div>}
            </div>
          )
        })}
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
          placeholder={authToken ? '输入您的问题...' : '请先登录后再和助手对话'}
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          disabled={loading || !authToken}
        />
        <button
          className="chat-send-btn"
          onClick={() => handleSend()}
          disabled={loading || !input.trim() || !authToken}
        >
          <Send size={18} />
        </button>
      </div>

      <div className="chat-footer">回复内容由 AI 助手生成，仅供参考</div>
    </div>
  )
}
