import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Upload, AlertCircle, FileCode, MessageSquare, Globe } from 'lucide-react'
import { createProduct, uploadSkill, getMe } from '../services/api'

const SUBCATEGORIES = {
  Agent: ['交易助手', '数据分析', '客服机器人', '内容生成', '研究助手', '其他'],
  Skill: ['文件处理', '数据转换', 'API调用', '文本处理', '图像处理', '其他'],
  Cron: ['定时监控', '数据同步', '报告生成', '备份任务', '价格追踪', '其他'],
  Workflow: ['自动化流程', 'CI/CD', '数据处理管线', '通知流程', '审批流程', '其他'],
}

const SKILL_TYPES = [
  { value: 'prompt', label: '提示词技能', icon: MessageSquare, desc: '上传 SKILL.md 提示词文件，平台加密托管，买家通过 API 调用执行' },
  { value: 'code', label: '代码技能包', icon: FileCode, desc: '上传 Python/JS 代码包，AES-256 加密存储，买家获得加密包 + License' },
  { value: 'sdk', label: '高码 SDK', icon: Globe, desc: '你自己部署服务，平台通过 SDK 协议控制权限和计费' },
]

export default function PublishPage({ userId, authToken }) {
  const navigate = useNavigate()
  const [form, setForm] = useState({
    name: '',
    description: '',
    category: '',
    subcategory: '',
    price: '',
    tags: '',
    content_preview: '',
    github_url: '',
    seller_name: '',
  })
  const [skillType, setSkillType] = useState('')
  const [skillFile, setSkillFile] = useState(null)
  const [sdkEndpoint, setSdkEndpoint] = useState('')
  const [publishing, setPublishing] = useState(false)
  const [error, setError] = useState('')
  const [step, setStep] = useState(1)

  const handleChange = (field, value) => {
    const updated = { ...form, [field]: value }
    if (field === 'category') {
      updated.subcategory = ''
    }
    setForm(updated)
  }

  const validate = () => {
    if (!form.name.trim()) return '请输入商品名称'
    if (!form.description.trim()) return '请输入商品描述'
    if (!form.category) return '请选择分类'
    if (!form.price || Number(form.price) <= 0) return '请输入有效的价格'
    if (step === 2 && !skillType) return '请选择技能类型'
    if (step === 2 && skillType === 'sdk' && !sdkEndpoint.trim()) return '请输入 SDK 服务地址'
    if (!form.seller_name.trim() && !authToken) return '请输入卖家名称'
    return null
  }

  const handleSubmit = async (e) => {
    e.preventDefault()
    const validationError = validate()
    if (validationError) {
      setError(validationError)
      return
    }

    setError('')
    setPublishing(true)

    try {
      const sellerName = form.seller_name.trim()
      if (!sellerName) {
        const lsNick = localStorage.getItem('skillbazaar_nickname')
        const lsUser = localStorage.getItem('skillbazaar_username')
        if (lsNick) {
          // localStorage has it, use it
        } else if (authToken) {
          // Fetch from API
          try {
            const me = await getMe(authToken)
            if (me?.nickname || me?.username) {
              localStorage.setItem('skillbazaar_nickname', me.nickname || '')
              localStorage.setItem('skillbazaar_username', me.username || '')
            }
          } catch {}
        }
      }
      const finalSellerName = form.seller_name.trim() || localStorage.getItem('skillbazaar_nickname') || localStorage.getItem('skillbazaar_username') || '匿名卖家'

      const payload = {
        name: form.name.trim(),
        description: form.description.trim(),
        category: form.category,
        sub_category: form.subcategory || null,
        price: Number(form.price),
        tags: form.tags
          .split(',')
          .map((t) => t.trim())
          .filter(Boolean) || [],
        content_preview: form.content_preview.trim() || null,
        github_url: form.github_url.trim() || null,
        seller_name: sellerName,
        source_platform: '原创',
      }

      const headers = authToken ? { Authorization: `Bearer ${authToken}` } : {}
      const data = await createProduct(payload, authToken)
      const productId = data.id || data.product_id

      if (skillType && productId) {
        try {
          await uploadSkill(
            productId,
            skillType,
            skillType !== 'sdk' ? skillFile : null,
            userId || 'anonymous',
            skillType === 'sdk' ? { sdk_endpoint: sdkEndpoint.trim() } : (skillFile ? null : { content: form.content_preview || form.description })
          )
        } catch (uploadErr) {
          console.error('Skill upload failed:', uploadErr)
        }
      }

      if (productId) {
        navigate(`/product/${productId}`)
      } else {
        navigate('/')
      }
    } catch (err) {
      setError(err?.detail || err?.message || '发布失败，请稍后重试')
    } finally {
      setPublishing(false)
    }
  }

  return (
    <div className="publish-page page-shell">
      <div className="publish-container">
        <h1 className="publish-title">
          <Upload size={28} />
          发布商品
        </h1>

        <div className="publish-steps">
          <button
            className={`step-btn ${step === 1 ? 'active' : 'done'}`}
            onClick={() => setStep(1)}
          >
            1. 基本信息
          </button>
          <button
            className={`step-btn ${step === 2 ? 'active' : step > 2 ? 'done' : ''}`}
            onClick={() => setStep(2)}
            disabled={!form.name || !form.category || !form.price}
          >
            2. 技能上传
          </button>
          <button
            className={`step-btn ${step === 3 ? 'active' : ''}`}
            onClick={() => setStep(3)}
          >
            3. 发布
          </button>
        </div>

        <form className="publish-form" onSubmit={handleSubmit}>
          {error && (
            <div className="form-error">
              <AlertCircle size={16} />
              {error}
            </div>
          )}

          {step >= 1 && (
            <div className={`step-content ${step === 1 ? '' : 'collapsed'}`}>
              <div className="form-group">
                <label className="form-label">
                  商品名称 <span className="required">*</span>
                </label>
                <input
                  type="text"
                  className="form-input"
                  placeholder="给您的商品起个名字"
                  value={form.name}
                  onChange={(e) => handleChange('name', e.target.value)}
                  maxLength={100}
                />
              </div>

              <div className="form-group">
                <label className="form-label">
                  商品描述 <span className="required">*</span>
                </label>
                <textarea
                  className="form-textarea"
                  placeholder="详细描述您的商品功能、用途和使用方法"
                  value={form.description}
                  onChange={(e) => handleChange('description', e.target.value)}
                  rows={5}
                  maxLength={2000}
                />
              </div>

              <div className="form-row">
                <div className="form-group form-group-half">
                  <label className="form-label">
                    分类 <span className="required">*</span>
                  </label>
                  <select
                    className="form-select"
                    value={form.category}
                    onChange={(e) => handleChange('category', e.target.value)}
                  >
                    <option value="">请选择分类</option>
                    {Object.keys(SUBCATEGORIES).map((cat) => (
                      <option key={cat} value={cat}>
                        {cat === 'Agent' && '🤖 '}
                        {cat === 'Skill' && '⚡ '}
                        {cat === 'Cron' && '⏰ '}
                        {cat === 'Workflow' && '🔄 '}
                        {cat}
                      </option>
                    ))}
                  </select>
                </div>

                <div className="form-group form-group-half">
                  <label className="form-label">子分类</label>
                  <select
                    className="form-select"
                    value={form.subcategory}
                    onChange={(e) => handleChange('subcategory', e.target.value)}
                    disabled={!form.category}
                  >
                    <option value="">请选择子分类</option>
                    {form.category &&
                      SUBCATEGORIES[form.category].map((sub) => (
                        <option key={sub} value={sub}>
                          {sub}
                        </option>
                      ))}
                  </select>
                </div>
              </div>

              <div className="form-row">
                <div className="form-group form-group-half">
                  <label className="form-label">
                    定价（金币） <span className="required">*</span>
                  </label>
                  <input
                    type="number"
                    className="form-input"
                    placeholder="输入价格"
                    value={form.price}
                    onChange={(e) => handleChange('price', e.target.value)}
                    min="1"
                  />
                </div>
                {!authToken && (
                  <div className="form-group form-group-half">
                    <label className="form-label">
                      卖家名称 <span className="required">*</span>
                    </label>
                    <input
                      type="text"
                      className="form-input"
                      placeholder="您的名称"
                      value={form.seller_name}
                      onChange={(e) => handleChange('seller_name', e.target.value)}
                    />
                  </div>
                )}
              </div>

              <div className="form-group">
                <label className="form-label">标签</label>
                <input
                  type="text"
                  className="form-input"
                  placeholder="用逗号分隔多个标签，如：交易,自动化,API"
                  value={form.tags}
                  onChange={(e) => handleChange('tags', e.target.value)}
                />
              </div>

              <div className="form-group">
                <label className="form-label">内容预览</label>
                <textarea
                  className="form-textarea form-textarea-code"
                  placeholder="粘贴 SKILL.md 或配置文件内容，供买家预览"
                  value={form.content_preview}
                  onChange={(e) => handleChange('content_preview', e.target.value)}
                  rows={8}
                  style={{ fontFamily: 'monospace' }}
                />
              </div>

              <div className="form-group">
                <label className="form-label">GitHub 地址</label>
                <input
                  type="text"
                  className="form-input"
                  placeholder="https://github.com/..."
                  value={form.github_url}
                  onChange={(e) => handleChange('github_url', e.target.value)}
                />
              </div>
            </div>
          )}

          {step >= 2 && (
            <div className={`step-content ${step === 2 ? '' : 'collapsed'}`}>
              <div className="form-group">
                <label className="form-label">技能类型</label>
                <div className="skill-type-selector">
                  {SKILL_TYPES.map((st) => (
                    <button
                      key={st.value}
                      type="button"
                      className={`skill-type-card ${skillType === st.value ? 'selected' : ''}`}
                      onClick={() => setSkillType(st.value)}
                    >
                      <st.icon size={24} />
                      <div className="skill-type-info">
                        <strong>{st.label}</strong>
                        <span>{st.desc}</span>
                      </div>
                    </button>
                  ))}
                </div>
              </div>

              {skillType === 'prompt' && (
                <div className="form-group">
                  <label className="form-label">上传提示词文件 (SKILL.md)</label>
                  <input
                    type="file"
                    className="form-input"
                    accept=".md,.txt,.json"
                    onChange={(e) => setSkillFile(e.target.files[0])}
                  />
                  <small className="form-hint">支持 .md .txt .json 格式，上传后将 AES-256 加密存储</small>
                </div>
              )}

              {skillType === 'code' && (
                <div className="form-group">
                  <label className="form-label">上传代码包</label>
                  <input
                    type="file"
                    className="form-input"
                    accept=".zip,.py,.js,.ts,.json"
                    onChange={(e) => setSkillFile(e.target.files[0])}
                  />
                  <small className="form-hint">支持 .zip .py .js .ts 格式，加密后买家只能通过 License 解密使用</small>
                </div>
              )}

              {skillType === 'sdk' && (
                <div className="form-group">
                  <label className="form-label">SDK 服务地址</label>
                  <input
                    type="text"
                    className="form-input"
                    placeholder="https://your-service.com/api/execute"
                    value={sdkEndpoint}
                    onChange={(e) => setSdkEndpoint(e.target.value)}
                  />
                  <small className="form-hint">你自己部署的服务端点，平台通过此地址调用并控制权限</small>
                </div>
              )}
            </div>
          )}

          <div className="publish-actions">
            {step > 1 && (
              <button
                type="button"
                className="btn btn-secondary"
                onClick={() => setStep(step - 1)}
              >
                上一步
              </button>
            )}
            {step < 3 ? (
              <button
                type="button"
                className="btn btn-primary"
                onClick={() => {
                  if (step === 1 && (!form.name || !form.category || !form.price)) {
                    setError('请先填写必要信息')
                    return
                  }
                  setStep(step + 1)
                  setError('')
                }}
              >
                下一步
              </button>
            ) : (
              <button type="submit" className="btn btn-primary btn-publish-submit" disabled={publishing}>
                {publishing ? '发布中...' : '加密并发布'}
              </button>
            )}
          </div>
        </form>
      </div>
    </div>
  )
}
