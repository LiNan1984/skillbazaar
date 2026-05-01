import { useState, useEffect } from 'react'
import { X, Wallet, ArrowUpCircle, ArrowDownCircle } from 'lucide-react'
import { getWalletHistory, rechargeCoins } from '../services/api'

const TX_TYPE_LABELS = {
  recharge: { label: '充值', icon: ArrowUpCircle, color: '#22c55e' },
  buy: { label: '购买', icon: ArrowDownCircle, color: '#ef4444' },
  sell: { label: '售卖收入', icon: ArrowUpCircle, color: '#22c55e' },
  refund: { label: '退款', icon: ArrowUpCircle, color: '#3b82f6' },
  promo: { label: '活动奖励', icon: ArrowUpCircle, color: '#a855f7' },
}

export default function WalletPanel({ onClose, token, coins }) {
  const [transactions, setTransactions] = useState([])
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [promoCode, setPromoCode] = useState('')
  const [rechargeMsg, setRechargeMsg] = useState('')

  useEffect(() => {
    loadHistory()
  }, [page])

  const loadHistory = async () => {
    try {
      const data = await getWalletHistory(page, token)
      setTransactions(data.transactions || [])
      setTotal(data.total || 0)
    } catch {}
  }

  const handleRecharge = async () => {
    if (!promoCode.trim()) return
    setRechargeMsg('')
    try {
      const data = await rechargeCoins(promoCode.trim(), token)
      if (data.success) {
        setRechargeMsg(`充值成功！+${data.coins_added} 金币`)
        setPromoCode('')
        loadHistory()
      }
    } catch (err) {
      setRechargeMsg(err?.detail || '充值码无效')
    }
  }

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="wallet-panel" onClick={(e) => e.stopPropagation()}>
        <button className="modal-close" onClick={onClose}><X size={20} /></button>

        <div className="wallet-header">
          <Wallet size={24} />
          <div>
            <h2>我的钱包</h2>
            <span className="wallet-balance">余额：¥{coins?.toLocaleString() || 0} 金币</span>
          </div>
        </div>

        <div className="wallet-recharge">
          <input
            type="text"
            className="form-input"
            placeholder="输入充值码"
            value={promoCode}
            onChange={(e) => setPromoCode(e.target.value)}
          />
          <button className="btn btn-primary" onClick={handleRecharge} disabled={!promoCode.trim()}>
            充值
          </button>
          {rechargeMsg && <span className="recharge-msg">{rechargeMsg}</span>}
        </div>

        <div className="wallet-history">
          <h3>交易记录</h3>
          {transactions.length === 0 ? (
            <p className="empty-hint">暂无交易记录</p>
          ) : (
            transactions.map((tx) => {
              const typeInfo = TX_TYPE_LABELS[tx.type] || { label: tx.type, icon: ArrowDownCircle, color: '#71717a' }
              const TypeIcon = typeInfo.icon
              return (
                <div key={tx.id} className="wallet-tx-item">
                  <div className="wallet-tx-left">
                    <TypeIcon size={18} style={{ color: typeInfo.color }} />
                    <div>
                      <span className="wallet-tx-desc">{tx.description || typeInfo.label}</span>
                      <span className="wallet-tx-time">{tx.created_at?.slice(0, 19) || ''}</span>
                    </div>
                  </div>
                  <span className="wallet-tx-amount" style={{ color: tx.amount > 0 ? '#22c55e' : '#ef4444' }}>
                    {tx.amount > 0 ? '+' : ''}{tx.amount}
                  </span>
                </div>
              )
            })
          )}
        </div>

        {total > 20 && (
          <div className="wallet-pagination">
            <button disabled={page <= 1} onClick={() => setPage(page - 1)}>上一页</button>
            <span>{page} / {Math.ceil(total / 20)}</span>
            <button disabled={page * 20 >= total} onClick={() => setPage(page + 1)}>下一页</button>
          </div>
        )}
      </div>
    </div>
  )
}
