import { useState, useEffect } from 'react'

const bountyData = [
  { title: '量化交易策略回测Agent开发', budget: '¥5,000-15,000', category: 'Agent', avatar: '🤖' },
  { title: 'RAG知识库构建与优化', budget: '¥8,000-20,000', category: 'Skill', avatar: '📚' },
  { title: 'AI客服智能体编排Workflow', budget: '¥10,000-30,000', category: 'Workflow', avatar: '🔄' },
  { title: '多模态文档理解Agent', budget: '¥12,000-35,000', category: 'Agent', avatar: '👁️' },
  { title: '智能代码审查Agent', budget: '¥6,000-18,000', category: 'Agent', avatar: '🔍' },
  { title: 'AI内容审核Agent', budget: '¥8,000-25,000', category: 'Agent', avatar: '🛡️' },
  { title: '竞品监控Cron服务', budget: '¥4,000-10,000', category: 'Cron', avatar: '📊' },
  { title: '数据管道ETL Workflow', budget: '¥6,000-15,000', category: 'Workflow', avatar: '🔧' },
]

const productData = [
  { title: 'LangGraph多Agent协作框架', price: '¥299', seller: '全栈Charlie', avatar: '⚡' },
  { title: 'AutoGPT自主任务执行Agent', price: '¥399', seller: '量化Alice', avatar: '🤖' },
  { title: '代码安全审计Agent', price: '¥199', seller: '安全Eve', avatar: '🔒' },
  { title: '智能客服对话Agent', price: '¥349', seller: 'API Judy', avatar: '💬' },
  { title: 'GPT-4 Turbo精调Prompt套件', price: '¥149', seller: '大模型Bob', avatar: '🎯' },
]

let pushIndex = 0

export default function PushNotification() {
  const [notification, setNotification] = useState(null)
  const [visible, setVisible] = useState(false)
  const [dismissed, setDismissed] = useState(new Set())

  useEffect(() => {
    // Show first notification after 3s, then every 8s
    const showNext = () => {
      let attempts = 0
      while (attempts < 20) {
        const idx = pushIndex % (bountyData.length + productData.length)
        pushIndex++
        if (dismissed.has(idx)) { attempts++; continue }
        
        let item
        let type
        if (idx < bountyData.length) {
          item = bountyData[idx]
          type = 'bounty'
        } else {
          item = productData[idx - bountyData.length]
          type = 'product'
        }
        
        setNotification({ ...item, type, idx })
        setVisible(true)
        
        // Auto dismiss after 6s
        setTimeout(() => {
          setVisible(false)
          setTimeout(() => setNotification(null), 400)
        }, 6000)
        break
      }
    }

    const timer1 = setTimeout(showNext, 3000)
    const interval = setInterval(showNext, 12000)
    return () => { clearTimeout(timer1); clearInterval(interval) }
  }, [dismissed])

  if (!notification) return null

  const handleDismiss = () => {
    setVisible(false)
    dismissed.add(notification.idx)
    setTimeout(() => setNotification(null), 400)
  }

  return (
    <div className={`push-notification ${visible ? 'push-in' : 'push-out'}`}>
      <div className="push-notification-header">
        <span className="push-badge">
          {notification.type === 'bounty' ? '🏆 新悬赏' : '🆕 新上架'}
        </span>
        <button className="push-close" onClick={handleDismiss}>✕</button>
      </div>
      <div className="push-notification-body">
        <span className="push-avatar">{notification.avatar}</span>
        <div className="push-info">
          <div className="push-title">{notification.title}</div>
          <div className="push-meta">
            {notification.type === 'bounty' 
              ? <span className="push-budget">{notification.budget}</span>
              : <><span className="push-price">{notification.price}</span><span className="push-seller">by {notification.seller}</span></>
            }
            <span className="push-category-tag">{notification.category}</span>
          </div>
        </div>
      </div>
      <div className="push-notification-footer">
        <span className="push-time">刚刚</span>
        <a href={notification.type === 'bounty' ? '/bounties' : '/'} className="push-action">
          {notification.type === 'bounty' ? '立即查看 →' : '去看看 →'}
        </a>
      </div>
    </div>
  )
}
