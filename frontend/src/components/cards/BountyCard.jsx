import { useState } from 'react'
import { createBounty } from '../../services/api'

const CATEGORIES = ['Agent', 'Skill', 'Cron', 'Workflow', 'Tool', 'Other']
const SKILL_TYPES = ['python', 'javascript', 'shell', 'api', 'other']

const INITIAL_FORM = {
  title: '',
  description: '',
  category: 'Skill',
  skill_type: 'python',
  budget_min: '',
  budget_max: '',
  deadline: '',
}

function buildInitialForm(card) {
  // v2 zero-result guidance (and do_bounty) prefill top-level data fields;
  // ongoing edits carry the form under data.form.
  if (card?.data?.form) return { ...INITIAL_FORM, ...card.data.form }
  const data = card?.data || {}
  return {
    ...INITIAL_FORM,
    title: data.title || '',
    description: data.description || '',
    category: CATEGORIES.includes(data.category) ? data.category : 'Skill',
    skill_type: SKILL_TYPES.includes(data.skill_type) ? data.skill_type : 'python',
    budget_min: data.budget_min ?? '',
    budget_max: data.budget_max ?? '',
    deadline: data.deadline || '',
  }
}

export default function BountyCard({ card, authToken, userId, onUpdate, onSubmit, onCancel }) {
  const [mode, setMode] = useState(card?.data?.mode || 'fill')
  const [form, setForm] = useState(buildInitialForm(card))
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState('')
  const [createdId, setCreatedId] = useState(card?.data?.createdId || null)

  const updateForm = (field, value) => {
    const next = { ...form, [field]: value }
    setForm(next)
    onUpdate?.({ ...card, data: { ...card.data, form: next, mode } })
  }

  const handlePreview = () => {
    if (!form.title.trim() || !form.description.trim()) {
      setError('请填写标题和描述')
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
      const data = {
        title: form.title,
        description: form.description,
        category: form.category,
        skill_type: form.skill_type,
        budget_min: parseFloat(form.budget_min) || 0,
        budget_max: parseFloat(form.budget_max) || 0,
        deadline: form.deadline || null,
        poster_id: userId,
      }
      const result = await createBounty(data, authToken)
      const bountyId = result.bounty_id || result.id
      setCreatedId(bountyId)
      setMode('done')
      onUpdate?.({ ...card, data: { ...card.data, form, mode: 'done', createdId: bountyId } })
      onSubmit?.(bountyId)
    } catch (err) {
      setError(err.detail || err.message || '发布悬赏失败，请重试')
    } finally {
      setSubmitting(false)
    }
  }

  if (mode === 'done') {
    return (
      <div className="publish-card publish-card-done">
        <div className="publish-card-success">悬赏发布成功！</div>
        <a href={`/bounty/${createdId}`} className="publish-card-link">
          查看悬赏详情
        </a>
      </div>
    )
  }

  if (mode === 'preview') {
    return (
      <div className="publish-card">
        <div className="publish-card-header">确认悬赏信息</div>
        <div className="publish-card-preview">
          <div className="publish-card-field">
            <span className="publish-card-label">标题：</span>
            <span>{form.title}</span>
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
            <span className="publish-card-label">Skill类型：</span>
            <span>{form.skill_type}</span>
          </div>
          <div className="publish-card-field">
            <span className="publish-card-label">预算：</span>
            <span>¥{form.budget_min || 0} - ¥{form.budget_max || 0}</span>
          </div>
          {form.deadline && (
            <div className="publish-card-field">
              <span className="publish-card-label">截止日期：</span>
              <span>{form.deadline}</span>
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
      <div className="publish-card-header">发布悬赏</div>
      <div className="publish-card-form">
        <div className="publish-card-field">
          <label className="publish-card-label">标题 *</label>
          <input
            className="publish-card-input"
            value={form.title}
            onChange={(e) => updateForm('title', e.target.value)}
            placeholder="悬赏标题"
          />
        </div>
        <div className="publish-card-field">
          <label className="publish-card-label">描述 *</label>
          <textarea
            className="publish-card-textarea"
            value={form.description}
            onChange={(e) => updateForm('description', e.target.value)}
            placeholder="悬赏需求描述"
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
            <label className="publish-card-label">Skill类型</label>
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
        </div>
        <div className="publish-card-row">
          <div className="publish-card-field">
            <label className="publish-card-label">最低预算</label>
            <input
              className="publish-card-input"
              type="number"
              value={form.budget_min}
              onChange={(e) => updateForm('budget_min', e.target.value)}
              placeholder="0"
              min="0"
            />
          </div>
          <div className="publish-card-field">
            <label className="publish-card-label">最高预算</label>
            <input
              className="publish-card-input"
              type="number"
              value={form.budget_max}
              onChange={(e) => updateForm('budget_max', e.target.value)}
              placeholder="0"
              min="0"
            />
          </div>
        </div>
        <div className="publish-card-field">
          <label className="publish-card-label">截止日期</label>
          <input
            className="publish-card-input"
            type="date"
            value={form.deadline}
            onChange={(e) => updateForm('deadline', e.target.value)}
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
