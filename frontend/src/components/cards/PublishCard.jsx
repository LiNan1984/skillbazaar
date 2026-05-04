import { useState, useRef } from 'react'
import { createProduct, uploadSkill } from '../../services/api'

const CATEGORIES = ['Agent', 'Skill', 'Cron', 'Workflow', 'Tool', 'Other']
const SKILL_TYPES = ['python', 'javascript', 'shell', 'api', 'other']

const INITIAL_FORM = {
  name: '',
  description: '',
  category: 'Skill',
  price: '',
  skill_type: 'python',
  file: null,
  tags: '',
}

export default function PublishCard({ card, authToken, userId, onUpdate, onSubmit, onCancel }) {
  const [mode, setMode] = useState(card?.data?.mode || 'fill')
  const [form, setForm] = useState(card?.data?.form || INITIAL_FORM)
  const [createdId, setCreatedId] = useState(card?.data?.createdId || null)
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState('')
  const fileRef = useRef(null)

  const updateForm = (field, value) => {
    const next = { ...form, [field]: value }
    setForm(next)
    onUpdate?.({ ...card, data: { ...card.data, form: next, mode } })
  }

  const handlePreview = () => {
    if (!form.name.trim() || !form.description.trim()) {
      setError('请填写名称和描述')
      return
    }
    setError('')
    setMode('preview')
    onUpdate?.({ ...card, data: { ...card.data, form, mode: 'preview' } })
  }

  const handleEdit = () => {
    setMode('fill')
    onUpdate?.({ ...card, data: { ...card.data, form, mode: 'fill' } })
  }

  const handleConfirm = async () => {
    setSubmitting(true)
    setError('')
    try {
      const payload = {
        name: form.name,
        description: form.description,
        category: form.category,
        price: parseFloat(form.price) || 0,
        seller_id: userId,
        tags: form.tags ? form.tags.split(',').map((t) => t.trim()).filter(Boolean) : [],
      }
      const result = await createProduct(payload, authToken)
      const productId = result.product_id || result.id

      if (form.file && productId) {
        await uploadSkill(productId, form.skill_type, form.file, userId, {})
      }

      setCreatedId(productId)
      setMode('done')
      onUpdate?.({ ...card, data: { ...card.data, form, mode: 'done', createdId: productId } })
      onSubmit?.(productId)
    } catch (err) {
      setError(err.detail || err.message || '发布失败，请重试')
    } finally {
      setSubmitting(false)
    }
  }

  if (mode === 'done') {
    return (
      <div className="publish-card publish-card-done">
        <div className="publish-card-success">发布成功！</div>
        <a href={`/product/${createdId}`} className="publish-card-link">
          查看商品详情
        </a>
      </div>
    )
  }

  if (mode === 'preview') {
    return (
      <div className="publish-card">
        <div className="publish-card-header">确认发布信息</div>
        <div className="publish-card-preview">
          <div className="publish-card-field">
            <span className="publish-card-label">名称：</span>
            <span>{form.name}</span>
          </div>
          <div className="publish-card-field">
            <span className="publish-card-label">描述：</span>
            <span>{form.description}</span>
          </div>
          <div className="publish-card-field">
            <span className="publish-card-label">分类：</span>
            <span>{form.category}</span>
          </div>
          <div className="publish-card-field">
            <span className="publish-card-label">价格：</span>
            <span>¥{form.price || 0}</span>
          </div>
          <div className="publish-card-field">
            <span className="publish-card-label">类型：</span>
            <span>{form.skill_type}</span>
          </div>
          {form.file && (
            <div className="publish-card-field">
              <span className="publish-card-label">文件：</span>
              <span>{form.file.name}</span>
            </div>
          )}
          {form.tags && (
            <div className="publish-card-field">
              <span className="publish-card-label">标签：</span>
              <span>{form.tags}</span>
            </div>
          )}
        </div>
        {error && <div className="publish-card-error">{error}</div>}
        <div className="publish-card-actions">
          <button className="publish-card-btn secondary" onClick={handleEdit}>
            编辑
          </button>
          <button className="publish-card-btn primary" onClick={handleConfirm} disabled={submitting}>
            {submitting ? '发布中...' : '确认发布'}
          </button>
        </div>
        {onCancel && (
          <button className="publish-card-btn cancel" onClick={onCancel}>
            取消
          </button>
        )}
      </div>
    )
  }

  return (
    <div className="publish-card">
      <div className="publish-card-header">发布商品</div>
      <div className="publish-card-form">
        <div className="publish-card-field">
          <label className="publish-card-label">名称 *</label>
          <input
            className="publish-card-input"
            value={form.name}
            onChange={(e) => updateForm('name', e.target.value)}
            placeholder="商品名称"
          />
        </div>
        <div className="publish-card-field">
          <label className="publish-card-label">描述 *</label>
          <textarea
            className="publish-card-textarea"
            value={form.description}
            onChange={(e) => updateForm('description', e.target.value)}
            placeholder="商品描述"
            rows={3}
          />
        </div>
        <div className="publish-card-row">
          <div className="publish-card-field">
            <label className="publish-card-label">分类</label>
            <select
              className="publish-card-select"
              value={form.category}
              onChange={(e) => updateForm('category', e.target.value)}
            >
              {CATEGORIES.map((c) => (
                <option key={c} value={c}>{c}</option>
              ))}
            </select>
          </div>
          <div className="publish-card-field">
            <label className="publish-card-label">价格</label>
            <input
              className="publish-card-input"
              type="number"
              value={form.price}
              onChange={(e) => updateForm('price', e.target.value)}
              placeholder="0"
              min="0"
            />
          </div>
        </div>
        <div className="publish-card-field">
          <label className="publish-card-label">Skill 类型</label>
          <select
            className="publish-card-select"
            value={form.skill_type}
            onChange={(e) => updateForm('skill_type', e.target.value)}
          >
            {SKILL_TYPES.map((t) => (
              <option key={t} value={t}>{t}</option>
            ))}
          </select>
        </div>
        <div className="publish-card-field">
          <label className="publish-card-label">上传文件</label>
          <input
            ref={fileRef}
            type="file"
            className="publish-card-file"
            onChange={(e) => updateForm('file', e.target.files[0] || null)}
          />
        </div>
        <div className="publish-card-field">
          <label className="publish-card-label">标签（逗号分隔）</label>
          <input
            className="publish-card-input"
            value={form.tags}
            onChange={(e) => updateForm('tags', e.target.value)}
            placeholder="标签1, 标签2"
          />
        </div>
      </div>
      {error && <div className="publish-card-error">{error}</div>}
      <div className="publish-card-actions">
        <button className="publish-card-btn primary" onClick={handlePreview}>
          预览
        </button>
        {onCancel && (
          <button className="publish-card-btn cancel" onClick={onCancel}>
            取消
          </button>
        )}
      </div>
    </div>
  )
}
