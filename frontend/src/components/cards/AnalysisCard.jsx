import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'

export default function AnalysisCard({ card }) {
  const recommendation = card?.data?.recommendation || card?.data?.text || '暂无分析数据'

  return (
    <div className="analysis-card">
      <div className="analysis-card-content">
        <ReactMarkdown remarkPlugins={[remarkGfm]}>{recommendation}</ReactMarkdown>
      </div>
    </div>
  )
}
