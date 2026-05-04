import { useState, useEffect, useRef } from 'react'
import { useSearchParams } from 'react-router-dom'
import { Play, Square, Lock, Unlock, MessageSquare, Key, Clock, Coins, Box, Send, Loader2, Copy, Check } from 'lucide-react'
import { startSandbox, stopSandbox, getSandboxStatus, executeCode, encryptAgent, decryptAgent, npcChat, getSandboxApiDocs, redeemPointsForQuota, getPointsBalance } from '../services/api'
import { useLang } from '../i18n'

const TABS_MAP = {
  sandbox: { zh: '沙盒执行', en: 'Execute', icon: Box },
  encrypt: { zh: '虾塘加密', en: 'Encrypt', icon: Lock },
  chat: { zh: 'AI对话', en: 'AI Chat', icon: MessageSquare },
  developer: { zh: '开发者', en: 'Developer', icon: Key },
}

function StatBadge({ icon: Icon, label, value, color }) {
  return (
    <div className="sb-stat-badge" style={color ? { borderColor: color + '40' } : {}}>
      <Icon size={16} style={{ color: color || 'var(--accent-primary)' }} />
      <span className="sb-stat-label">{label}</span>
      <span className="sb-stat-value" style={color ? { color } : {}}>{value}</span>
    </div>
  )
}

function SandboxTab({ authToken, sandboxStatus, onStart, onStop, onExecute, loading, t }) {
  const [code, setCode] = useState(`# 🦐 Python in Sandbox
import json

result = {"shrimp": "power", "value": 42}
print(json.dumps(result, ensure_ascii=False, indent=2))`)
  const [output, setOutput] = useState('')
  const [executing, setExecuting] = useState(false)
  const running = sandboxStatus?.status === 'running'

  const handleExecute = async () => {
    setExecuting(true)
    setOutput('⏳ ...')
    try {
      const res = await onExecute(code, false, 'python')
      setOutput(res.stdout || res.output || res.stderr || res.error || 'No output')
    } catch (e) {
      setOutput('❌ ' + (e.message || 'Error'))
    } finally {
      setExecuting(false)
    }
  }

  return (
    <div className="sb-tab-content">
      <div className="sb-sandbox-grid">
        <div className="sb-editor-card">
          <div className="sb-editor-header">
            <span className="sb-editor-title"><Play size={14} /> {t('sb.editor')}</span>
            <span className="sb-editor-lang">Python 3</span>
          </div>
          <textarea className="sb-editor-textarea" value={code} onChange={(e) => setCode(e.target.value)} placeholder="Code..." spellCheck={false} />
          <div className="sb-editor-actions">
            <button className="btn btn-primary" onClick={handleExecute} disabled={!running || executing}>
              {executing ? <Loader2 size={16} className="sb-spin" /> : <Play size={16} />}
              {executing ? t('sb.executing') : t('sb.runCode')}
            </button>
            {!running && <span className="sb-hint">{t('sb.startFirst')}</span>}
          </div>
        </div>
        <div className="sb-output-card">
          <div className="sb-editor-header">
            <span className="sb-editor-title">{t('sb.output')}</span>
          </div>
          <pre className="sb-output-content">
            {running ? (output || t('sb.clickRun')) : t('sb.notRunning')}
          </pre>
        </div>
      </div>
    </div>
  )
}

function EncryptTab({ authToken, sandboxStatus, t }) {
  const [agentCode, setAgentCode] = useState('')
  const [agentName, setAgentName] = useState('')
  const [encrypted, setEncrypted] = useState('')
  const [decryptResult, setDecryptResult] = useState('')
  const [encrypting, setEncrypting] = useState(false)
  const [decrypting, setDecrypting] = useState(false)
  const [copied, setCopied] = useState(false)

  const handleEncrypt = async () => {
    if (!agentCode.trim()) return
    setEncrypting(true)
    try {
      const res = await encryptAgent(agentName || 'my-agent', agentCode, authToken)
      setEncrypted(res.encrypted_blob || res.encrypted || '')
    } catch (e) {
      setEncrypted('Failed: ' + (e.message || 'Error'))
    } finally {
      setEncrypting(false)
    }
  }

  const handleDecrypt = async () => {
    if (!encrypted.trim()) return
    setDecrypting(true)
    try {
      const res = await decryptAgent(encrypted, authToken)
      setDecryptResult(res.code || res.source_code || JSON.stringify(res, null, 2))
    } catch (e) {
      setDecryptResult('Failed: ' + (e.message || 'Error'))
    } finally {
      setDecrypting(false)
    }
  }

  const handleCopy = () => {
    navigator.clipboard?.writeText(encrypted)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  return (
    <div className="sb-tab-content">
      <div className="sb-encrypt-info">
        <Lock size={16} />
        <span>{t('sb.encrypt.info')}</span>
      </div>
      <div className="sb-sandbox-grid">
        <div className="sb-editor-card">
          <div className="sb-editor-header">
            <span className="sb-editor-title">{t('sb.agentSource')}</span>
            <input className="sb-input-sm" value={agentName} onChange={(e) => setAgentName(e.target.value)} placeholder={t('sb.agentName')} />
          </div>
          <textarea className="sb-editor-textarea sb-editor-small" value={agentCode} onChange={(e) => setAgentCode(e.target.value)} placeholder={t('sb.enterSource')} spellCheck={false} />
          <div className="sb-editor-actions">
            <button className="btn btn-primary" onClick={handleEncrypt} disabled={encrypting || !agentCode.trim()}>
              {encrypting ? <Loader2 size={16} className="sb-spin" /> : <Lock size={16} />}
              {t('sb.encrypt')}
            </button>
          </div>
        </div>
        <div className="sb-output-card">
          <div className="sb-editor-header">
            <span className="sb-editor-title">{t('sb.encryptedResult')}</span>
            {encrypted && (
              <button className="sb-copy-btn" onClick={handleCopy}>
                {copied ? <Check size={14} /> : <Copy size={14} />}
              </button>
            )}
          </div>
          <textarea className="sb-editor-textarea sb-editor-small" value={encrypted} readOnly placeholder={t('sb.blobPlaceholder')} />
          <div className="sb-editor-actions" style={{ marginTop: 12 }}>
            <button className="btn btn-ghost" onClick={handleDecrypt} disabled={decrypting || !encrypted.trim()}>
              {decrypting ? <Loader2 size={16} className="sb-spin" /> : <Unlock size={16} />}
              {t('sb.decryptVerify')}
            </button>
          </div>
          {decryptResult && <pre className="sb-output-content" style={{ marginTop: 12 }}>{decryptResult}</pre>}
        </div>
      </div>
    </div>
  )
}

function ChatTab({ authToken, sandboxRunning, initialMessage, t }) {
  const [messages, setMessages] = useState([])
  const [input, setInput] = useState('')
  const [sending, setSending] = useState(false)
  const messagesEnd = useRef(null)
  const initialSent = useRef(false)

  const scrollToBottom = () => {
    messagesEnd.current?.scrollIntoView({ behavior: 'smooth' })
  }

  useEffect(() => { scrollToBottom() }, [messages])

  // Auto-send initial message from skill redirect
  useEffect(() => {
    if (initialMessage && sandboxRunning && !initialSent.current) {
      initialSent.current = true
      setInput(initialMessage)
      // Auto-trigger send
      handleSendMsg(initialMessage)
    }
  }, [initialMessage, sandboxRunning])

  const handleSendMsg = async (msg) => {
    const userMsg = msg.trim()
    if (!userMsg || sending) return
    setInput('')
    setMessages(prev => [...prev, { role: 'user', content: userMsg }])
    setSending(true)
    try {
      const res = await npcChat(authToken, userMsg)
      setMessages(prev => [...prev, { role: 'assistant', content: res.reply || res.response || 'No reply' }])
    } catch (e) {
      setMessages(prev => [...prev, { role: 'assistant', content: '❌ ' + (e.message || 'Error') }])
    } finally {
      setSending(false)
    }
  }

  const handleSend = () => handleSendMsg(input)

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSend()
    }
  }

  return (
    <div className="sb-tab-content">
      {!sandboxRunning ? (
        <div className="sb-empty-state">
          <MessageSquare size={48} />
          <p>{t('sb.chat.startFirst')}</p>
        </div>
      ) : (
        <div className="sb-chat-container">
          <div className="sb-chat-messages">
            {messages.length === 0 && (
              <div className="sb-chat-welcome">
                <span className="sb-shrimp-icon">🦐</span>
                <p>{t('sb.chat.ready')}</p>
                <p className="sb-chat-hint">{t('sb.chat.hint')}</p>
              </div>
            )}
            {messages.map((msg, i) => (
              <div key={i} className={`sb-chat-bubble sb-chat-${msg.role}`}>
                {msg.role === 'assistant' && <span className="sb-chat-avatar">🦐</span>}
                <div className="sb-chat-text">{msg.content}</div>
              </div>
            ))}
            {sending && (
              <div className="sb-chat-bubble sb-chat-assistant">
                <span className="sb-chat-avatar">🦐</span>
                <div className="sb-chat-text sb-chat-typing">
                  <Loader2 size={16} className="sb-spin" /> {t('sb.chat.thinking')}
                </div>
              </div>
            )}
            <div ref={messagesEnd} />
          </div>
          <div className="sb-chat-input-bar">
            <input
              className="sb-chat-input"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder={t('sb.chat.placeholder')}
              disabled={sending}
            />
            <button className="btn btn-primary sb-chat-send" onClick={handleSend} disabled={!input.trim() || sending}>
              <Send size={16} />
            </button>
          </div>
        </div>
      )}
    </div>
  )
}

function DeveloperTab({ authToken, sandboxStatus, t }) {
  const [apiDocs, setApiDocs] = useState(null)
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    if (authToken) {
      setLoading(true)
      getSandboxApiDocs(authToken)
        .then(d => setApiDocs(d))
        .catch(() => setApiDocs(null))
        .finally(() => setLoading(false))
    }
  }, [authToken])

  return (
    <div className="sb-tab-content">
      <div className="sb-encrypt-info">
        <Key size={16} />
        <span>{t('sb.dev.info')}</span>
      </div>
      <div className="sb-dev-section">
        <h3 className="sb-section-title">{t('sb.dev.endpoint')}</h3>
        <div className="sb-api-list">
          <div className="sb-api-item">
            <span className="sb-api-method sb-api-post">POST</span>
            <code className="sb-api-path">/api/sandbox/chat</code>
            <span className="sb-api-desc">{t('sb.dev.openaiChat')}</span>
          </div>
          <div className="sb-api-item">
            <span className="sb-api-method sb-api-post">POST</span>
            <code className="sb-api-path">/api/sandbox/execute</code>
            <span className="sb-api-desc">{t('sb.dev.execute')}</span>
          </div>
          <div className="sb-api-item">
            <span className="sb-api-method sb-api-get">GET</span>
            <code className="sb-api-path">/api/sandbox/status</code>
            <span className="sb-api-desc">{t('sb.dev.status')}</span>
          </div>
          <div className="sb-api-item">
            <span className="sb-api-method sb-api-post">POST</span>
            <code className="sb-api-path">/api/sandbox/encrypt-agent</code>
            <span className="sb-api-desc">{t('sb.dev.encryptAgent')}</span>
          </div>
          <div className="sb-api-item">
            <span className="sb-api-method sb-api-post">POST</span>
            <code className="sb-api-path">/api/sandbox/decrypt-agent</code>
            <span className="sb-api-desc">{t('sb.dev.decryptAgent')}</span>
          </div>
        </div>
      </div>
      <div className="sb-dev-section">
        <h3 className="sb-section-title">{t('sb.dev.example')}</h3>
        <div className="sb-code-block">
          <pre>{`# Start sandbox
curl -X POST https://skillbazaar.harness-agent.app/api/sandbox/start?language=python \\
  -H "Authorization: Bearer ***"

# NPC Chat
curl -X POST https://skillbazaar.harness-agent.app/api/sandbox/chat \\
  -H "Authorization: Bearer ***" \\
  -H "Content-Type: application/json" \\
  -d '{"message": "Hello"}'

# Execute code
curl -X POST https://skillbazaar.harness-agent.app/api/sandbox/execute \\
  -H "Authorization: Bearer ***" \\
  -H "Content-Type: application/json" \\
  -d '{"code": "print(1+1)", "language": "python"}'`}</pre>
        </div>
      </div>
    </div>
  )
}

export default function SandboxPage({ authToken, onLoginClick }) {
  const [searchParams] = useSearchParams()
  const { t, lang } = useLang()
  const [activeTab, setActiveTab] = useState(() => {
    const tab = searchParams.get('tab')
    return tab && TABS_MAP[tab] ? tab : 'sandbox'
  })
  const [sandboxData, setSandboxData] = useState(null)
  const [loading, setLoading] = useState(false)
  const [points, setPoints] = useState(null)
  const [redeemHours, setRedeemHours] = useState(1)
  const [redeeming, setRedeeming] = useState(false)

  // Skill redirect: ?agent=xxx
  const skillAgent = searchParams.get('agent') || ''
  const skillMsg = searchParams.get('msg') || ''
  const initialMessage = skillAgent ? `[Skill: ${skillAgent}] ${skillMsg || '请帮我使用这个技能'}` : ''

  // If redirected from skill, switch to chat tab
  useEffect(() => {
    if (skillAgent && activeTab !== 'chat') {
      setActiveTab('chat')
    }
  }, [skillAgent])

  const loadStatus = async () => {
    if (!authToken) return
    try {
      const s = await getSandboxStatus(authToken)
      setSandboxData(s)
    } catch {
      setSandboxData(null)
    }
  }

  const loadPoints = async () => {
    if (!authToken) return
    try {
      const p = await getPointsBalance(authToken)
      setPoints(p)
    } catch {
      setPoints(null)
    }
  }

  useEffect(() => { loadStatus(); loadPoints() }, [authToken])

  const sandboxStatus = sandboxData?.sandbox || sandboxData
  const running = sandboxStatus?.status === 'running'
  const remainingMin = sandboxData?.remaining_seconds ? Math.floor(sandboxData.remaining_seconds / 60) : 0

  const handleStart = async () => {
    setLoading(true)
    try {
      await startSandbox('python', authToken)
      await loadStatus()
    } catch (e) {
      alert(e.message || 'Start failed')
    } finally {
      setLoading(false)
    }
  }

  const handleStop = async () => {
    setLoading(true)
    try {
      await stopSandbox(authToken)
      setSandboxData(null)
    } catch (e) {
      alert(e.message || 'Stop failed')
    } finally {
      setLoading(false)
    }
  }

  const handleExecute = async (code, encrypted, language) => {
    return await executeCode(code, language, encrypted, authToken)
  }

  const handleRedeem = async () => {
    setRedeeming(true)
    try {
      await redeemPointsForQuota(authToken, redeemHours)
      await loadStatus()
      await loadPoints()
    } catch (e) {
      alert(e.message || 'Redeem failed')
    } finally {
      setRedeeming(false)
    }
  }

  if (!authToken) {
    return (
      <div className="sb-page">
        <div className="sb-empty-state sb-login-prompt">
          <Box size={64} style={{ opacity: 0.3 }} />
          <h2>{t('sb.title')}</h2>
          <p>{t('sb.loginDesc')}</p>
          <button className="btn btn-primary" onClick={onLoginClick}>{t('sb.loginPrompt')}</button>
        </div>
      </div>
    )
  }

  const TABS = Object.entries(TABS_MAP).map(([id, cfg]) => ({
    id,
    label: cfg[lang] || cfg.zh,
    icon: cfg.icon,
  }))

  return (
    <div className="sb-page">
      {/* Header */}
      <div className="sb-header">
        <div className="sb-header-left">
          <h1 className="sb-title">{t('sb.title')}</h1>
          <p className="sb-subtitle">{t('sb.subtitle')}</p>
        </div>
        <div className="sb-header-stats">
          <StatBadge icon={Clock} label={t('sb.remain')} value={`${remainingMin}${t('sb.minutes')}`} color={running ? '#22c55e' : '#71717a'} />
          <StatBadge icon={Coins} label={t('sb.points')} value={points?.balance || 0} color="#eab308" />
          <StatBadge icon={Box} label={t('sb.status')} value={running ? t('sb.running') : t('sb.stopped')} color={running ? '#22c55e' : '#71717a'} />
        </div>
      </div>

      {/* Control Bar */}
      <div className="sb-control-bar">
        <div className="sb-control-left">
          {!running ? (
            <button className="btn btn-primary" onClick={handleStart} disabled={loading}>
              <Play size={16} /> {t('sb.start')}
            </button>
          ) : (
            <button className="btn btn-ghost sb-btn-danger" onClick={handleStop} disabled={loading}>
              <Square size={16} /> {t('sb.stop')}
            </button>
          )}
        </div>
        <div className="sb-redeem-section">
          <input type="number" className="sb-redeem-input" min="1" max="24" value={redeemHours} onChange={(e) => setRedeemHours(parseInt(e.target.value) || 1)} />
          <span className="sb-redeem-label">{t('sb.hours')}</span>
          <button className="btn btn-ghost sb-btn-redeem" onClick={handleRedeem} disabled={redeeming}>
            <Coins size={14} /> {t('sb.redeem')}
          </button>
          <span className="sb-redeem-hint">{t('sb.redeemHint')}</span>
        </div>
      </div>

      {/* Skill redirect banner */}
      {skillAgent && (
        <div className="sb-skill-banner">
          <span>🦐 {lang === 'zh' ? `正在加载技能「${skillAgent}」到NPC Agent...` : `Loading skill "${skillAgent}" into NPC Agent...`}</span>
        </div>
      )}

      {/* Tabs */}
      <div className="sb-tabs">
        {TABS.map(tab => (
          <button
            key={tab.id}
            className={`sb-tab ${activeTab === tab.id ? 'sb-tab-active' : ''}`}
            onClick={() => setActiveTab(tab.id)}
          >
            <tab.icon size={16} />
            {tab.label}
          </button>
        ))}
      </div>

      {/* Tab Content */}
      {activeTab === 'sandbox' && (
        <SandboxTab authToken={authToken} sandboxStatus={sandboxStatus} onStart={handleStart} onStop={handleStop} onExecute={handleExecute} loading={loading} t={t} />
      )}
      {activeTab === 'encrypt' && (
        <EncryptTab authToken={authToken} sandboxStatus={sandboxStatus} t={t} />
      )}
      {activeTab === 'chat' && (
        <ChatTab authToken={authToken} sandboxRunning={running} initialMessage={initialMessage} t={t} />
      )}
      {activeTab === 'developer' && (
        <DeveloperTab authToken={authToken} sandboxStatus={sandboxStatus} t={t} />
      )}
    </div>
  )
}
