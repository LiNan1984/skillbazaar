import { useState, useEffect, useCallback } from 'react'
import { Star, MessageSquarePlus } from 'lucide-react'
import { getProductReviews, createProductReview } from '../services/api'

const PAGE_SIZE = 10

function Stars({ value, size = 14, interactive = false, onChange }) {
  return (
    <span className={`review-stars ${interactive ? 'interactive' : ''}`}>
      {[1, 2, 3, 4, 5].map((n) => (
        <button
          key={n}
          type="button"
          disabled={!interactive}
          onClick={() => interactive && onChange?.(n)}
          className={interactive ? 'review-star-btn' : 'review-star-static'}
          aria-label={`${n} 星`}
        >
          <Star
            size={size}
            style={{ color: n <= value ? '#eab308' : '#4a4a58', fill: n <= value ? '#eab308' : 'none' }}
          />
        </button>
      ))}
    </span>
  )
}

function relativeTime(iso) {
  if (!iso) return ''
  const then = new Date(iso.includes('T') ? iso : iso.replace(' ', 'T'))
  const diffSec = Math.max(0, Math.floor((Date.now() - then.getTime()) / 1000))
  if (diffSec < 3600) return '刚刚'
  if (diffSec < 86400) return `${Math.floor(diffSec / 3600)} 小时前`
  if (diffSec < 86400 * 30) return `${Math.floor(diffSec / 86400)} 天前`
  return then.toLocaleDateString()
}

export default function ProductReviews({ productId, owned, authToken, userId, onRatingChange }) {
  const [items, setItems] = useState([])
  const [summary, setSummary] = useState({ avg_rating: 0, total: 0 })
  const [page, setPage] = useState(1)
  const [pages, setPages] = useState(1)
  const [loading, setLoading] = useState(true)
  const [rating, setRating] = useState(5)
  const [content, setContent] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState('')

  const loadPage = useCallback(async (pageNum, append = false) => {
    try {
      const data = await getProductReviews(productId, pageNum, PAGE_SIZE)
      setItems((prev) => (append ? [...prev, ...(data.items || [])] : (data.items || [])))
      setSummary(data.summary || { avg_rating: 0, total: 0 })
      setPages(data.pages || 1)
      setPage(pageNum)
    } catch {
      if (!append) {
        setItems([])
        setSummary({ avg_rating: 0, total: 0 })
      }
    } finally {
      setLoading(false)
    }
  }, [productId])

  useEffect(() => {
    setLoading(true)
    loadPage(1)
  }, [loadPage])

  useEffect(() => {
    if (summary.total > 0 && onRatingChange) {
      onRatingChange(summary.avg_rating)
    }
  }, [summary, onRatingChange])

  const myReview = items.find((r) => userId && String(r.user_id) === String(userId))
  const canReview = Boolean(authToken && owned && !myReview)

  const handleSubmit = async () => {
    if (submitting) return
    if (rating < 1 || rating > 5) return
    if (content.length > 500) return
    setSubmitting(true)
    setError('')
    try {
      const data = await createProductReview(productId, rating, content.trim(), authToken)
      const created = data.review
      // optimistic-free: insert the server row at the top and refresh summary
      setItems((prev) => [created, ...prev])
      setSummary(data.summary || { total: summary.total + 1, avg_rating: rating })
      setPages(1)
      setContent('')
      setRating(5)
    } catch (e) {
      setError(e?.detail || '评价提交失败，请稍后重试')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="detail-section review-section">
      <h2 className="review-section-title">
        用户评价
        <span className="review-summary">
          {summary.total > 0 ? (
            <>
              <Star size={15} style={{ color: '#eab308', fill: '#eab308' }} />
              <strong>{Number(summary.avg_rating).toFixed(1)}</strong>
              <span className="review-summary-total">· {summary.total} 条</span>
            </>
          ) : (
            <span className="review-summary-empty">暂无评价</span>
          )}
        </span>
      </h2>

      {!authToken && (
        <div className="review-guide">
          <MessageSquarePlus size={16} />
          <span>登录并购买后即可评价该商品</span>
        </div>
      )}

      {authToken && !owned && !myReview && (
        <div className="review-guide">
          <MessageSquarePlus size={16} />
          <span>购买后可评价该商品，您的反馈将帮助其他买家做出选择</span>
        </div>
      )}

      {myReview && (
        <div className="review-mine">
          <div className="review-mine-header">
            <span className="review-mine-label">我的评价</span>
            <Stars value={myReview.rating} />
            <span className="review-time">{relativeTime(myReview.created_at)}</span>
          </div>
          {myReview.content && <p className="review-mine-content">{myReview.content}</p>}
        </div>
      )}

      {canReview && (
        <div className="review-form">
          <div className="review-form-row">
            <span className="review-form-label">我的评分：</span>
            <Stars value={rating} interactive onChange={setRating} />
          </div>
          <textarea
            className="review-textarea"
            placeholder="说说这款商品的使用体验（最多 500 字）"
            maxLength={500}
            value={content}
            onChange={(e) => setContent(e.target.value)}
            rows={3}
          />
          <div className="review-form-footer">
            <span className={`review-char-count ${content.length >= 500 ? 'limit' : ''}`}>
              {content.length}/500
            </span>
            {error && <span className="review-form-error">{error}</span>}
            <button
              className="btn btn-primary btn-sm review-submit-btn"
              onClick={handleSubmit}
              disabled={submitting}
            >
              {submitting ? '提交中...' : '发表评价'}
            </button>
          </div>
        </div>
      )}

      <div className="review-list">
        {loading ? (
          <p className="review-empty-text">加载中...</p>
        ) : items.length === 0 ? (
          <p className="review-empty-text">还没有评价，成为第一个评价的买家吧。</p>
        ) : (
          items.map((review) => (
            <div key={review.id} className="review-item">
              <img
                className="review-avatar"
                src={review.avatar || `https://api.dicebear.com/7.x/bottts/svg?seed=${review.nickname || review.user_id}`}
                alt={review.nickname || '用户'}
              />
              <div className="review-item-body">
                <div className="review-item-header">
                  <span className="review-nickname">{review.nickname || '匿名用户'}</span>
                  <Stars value={review.rating} />
                  <span className="review-time">{relativeTime(review.created_at)}</span>
                </div>
                {review.content && <p className="review-content">{review.content}</p>}
              </div>
            </div>
          ))
        )}
      </div>

      {page < pages && (
        <button className="btn btn-ghost btn-sm review-load-more" onClick={() => loadPage(page + 1, true)}>
          加载更多评价
        </button>
      )}
    </div>
  )
}
