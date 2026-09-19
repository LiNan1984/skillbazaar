export default function FloatingAssistant({ isOpen, onClick }) {
  return (
    <div
      className={`floating-assistant ${isOpen ? 'active' : ''}`}
      role="button"
      tabIndex={0}
      aria-label="BS买卖助手"
      onClick={onClick}
      onKeyDown={(e) => {
        if (e.key === 'Enter' || e.key === ' ') {
          e.preventDefault()
          onClick()
        }
      }}
    >
      <img src="/logo.png" alt="BS买卖助手" style={{ width: 32, height: 32, borderRadius: 8, objectFit: 'cover' }} />
      <span className="floating-assistant-tooltip">BS买卖助手</span>
    </div>
  )
}
