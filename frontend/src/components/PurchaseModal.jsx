import { useState } from 'react'
import { X, CheckCircle, AlertCircle } from 'lucide-react'
import { buyProduct } from '../services/api'

export default function PurchaseModal({ product, userId, balance, onClose, onSuccess }) {
  const [purchasing, setPurchasing] = useState(false)
  const [success, setSuccess] = useState(false)
  const [error, setError] = useState('')

  const insufficient = balance < (product?.price ?? 0)

  const handlePurchase = async () => {
    if (insufficient || purchasing) return
    setPurchasing(true)
    setError('')

    try {
      await buyProduct(userId, product.id)
      setSuccess(true)
      setTimeout(() => {
        if (onSuccess) onSuccess()
        onClose()
      }, 1500)
    } catch (err) {
      setError(err?.detail || err?.message || '购买失败，请稍后重试')
    } finally {
      setPurchasing(false)
    }
  }

  if (!product) return null

  const categoryEmoji =
    product.category === 'Agent'
      ? '🤖'
      : product.category === 'Skill'
        ? '⚡'
        : product.category === 'Cron'
          ? '⏰'
          : '🔄'

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-content" onClick={(e) => e.stopPropagation()}>
        <button className="modal-close" onClick={onClose}>
          <X size={20} />
        </button>

        {success ? (
          <div className="purchase-success">
            <CheckCircle size={64} className="success-icon" />
            <h3>购买成功!</h3>
            <p>「{product.name}」已添加到您的库中</p>
          </div>
        ) : (
          <>
            <h2 className="modal-title">确认购买</h2>

            <div className="purchase-info">
              <div className="purchase-product">
                <span className="purchase-product-icon">{categoryEmoji}</span>
                <div>
                  <h4>{product.name}</h4>
                  <p className="purchase-product-category">{product.category}</p>
                </div>
              </div>

              <div className="purchase-price-row">
                <span className="purchase-label">商品价格</span>
                <span className="purchase-value price">{'\uFFE5'}{product.price} 金币</span>
              </div>

              <div className="purchase-price-row">
                <span className="purchase-label">当前余额</span>
                <span className={`purchase-value ${insufficient ? 'insufficient' : 'sufficient'}`}>
                  {'\uFFE5'}{balance.toLocaleString()} 金币
                </span>
              </div>

              {insufficient && (
                <div className="purchase-error-msg">
                  <AlertCircle size={16} />
                  余额不足，请先充值
                </div>
              )}

              {error && (
                <div className="purchase-error-msg">
                  <AlertCircle size={16} />
                  {error}
                </div>
              )}
            </div>

            <div className="modal-actions">
              <button className="btn btn-ghost" onClick={onClose} disabled={purchasing}>
                取消
              </button>
              <button
                className="btn btn-primary btn-purchase"
                onClick={handlePurchase}
                disabled={insufficient || purchasing}
              >
                {purchasing ? '购买中...' : '确认购买'}
              </button>
            </div>
          </>
        )}
      </div>
    </div>
  )
}
