export default function FloatingAssistant({ isOpen, onClick }) {
  return (
    <div
      className={`floating-assistant ${isOpen ? 'active' : ''}`}
      onClick={onClick}
    >
      <svg
        className="floating-assistant-icon"
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
      >
        <rect x="3" y="11" width="18" height="10" rx="2" />
        <circle cx="9" cy="16" r="1" />
        <circle cx="15" cy="16" r="1" />
        <path d="M8 11V7a4 4 0 0 1 8 0v4" />
        <path d="M12 2v2" />
        <path d="M9 4h6" />
      </svg>
      <span className="floating-assistant-tooltip">BS买卖助手</span>
    </div>
  )
}
