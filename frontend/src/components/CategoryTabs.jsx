import { useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'

const CATEGORIES = [
  { key: '', label: '全部', icon: null },
  { key: 'Agent', label: 'Agent', icon: '🤖' },
  { key: 'Skill', label: 'Skill', icon: '⚡' },
  { key: 'Cron', label: 'Cron', icon: '⏰' },
  { key: 'Workflow', label: 'Workflow', icon: '🔄' },
]

const SUBCATEGORIES = {
  Agent: ['交易助手', '数据分析', '客服机器人', '内容生成', '研究助手', '其他'],
  Skill: ['文件处理', '数据转换', 'API调用', '文本处理', '图像处理', '其他'],
  Cron: ['定时监控', '数据同步', '报告生成', '备份任务', '价格追踪', '其他'],
  Workflow: ['自动化流程', 'CI/CD', '数据处理管线', '通知流程', '审批流程', '其他'],
}

export default function CategoryTabs() {
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  const category = searchParams.get('category') || ''
  const subcategory = searchParams.get('subcategory') || ''

  const updateFilter = (key, value) => {
    const params = new URLSearchParams(searchParams)
    if (value) {
      params.set(key, value)
    } else {
      params.delete(key)
    }
    if (key === 'category') {
      params.delete('subcategory')
    }
    navigate(`/?${params.toString()}`)
  }

  const subs = category && SUBCATEGORIES[category] ? SUBCATEGORIES[category] : []

  return (
    <div className="category-tabs-container">
      <div className="category-tabs-inner">
        <div className="category-tabs-row">
          {CATEGORIES.map((cat) => (
            <button
              key={cat.key}
              className={`category-tab ${category === cat.key ? 'active' : ''}`}
              onClick={() => updateFilter('category', cat.key === '' ? '' : cat.key)}
            >
              {cat.icon && <span className="category-tab-icon">{cat.icon}</span>}
              {cat.label}
            </button>
          ))}
        </div>

        {subs.length > 0 && (
          <div className="category-subtabs-row">
            <button
              className={`category-subtab ${subcategory === '' ? 'active' : ''}`}
              onClick={() => updateFilter('subcategory', '')}
            >
              全部
            </button>
            {subs.map((sub) => (
              <button
                key={sub}
                className={`category-subtab ${subcategory === sub ? 'active' : ''}`}
                onClick={() => updateFilter('subcategory', sub)}
              >
                {sub}
              </button>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
