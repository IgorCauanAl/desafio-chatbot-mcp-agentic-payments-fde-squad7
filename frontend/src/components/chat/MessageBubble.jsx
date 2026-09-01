import ToolCallCard from './ToolCallCard.jsx';
import './messageBubble.css';

function buildQuickReplies(content = '') {
  const normalized = content.toLowerCase();

  if (normalized.includes('como você prefere pagar')) {
    return ['Cartão', 'Pix'];
  }

  if (normalized.includes('você confirma')) {
    return ['Sim', 'Não'];
  }

  return [];
}

export default function MessageBubble({ message, onReply, loading }) {
  const isUser = message.role === 'user';
  const quickReplies = !isUser ? buildQuickReplies(message.content) : [];

  return (
    <div className={`bubble-row ${isUser ? 'bubble-row--user' : ''}`}>
      <div className={`bubble ${isUser ? 'bubble--user' : 'bubble--agent'}`}>
        <p>{message.content}</p>
        {message.toolCall && <ToolCallCard toolCall={message.toolCall} />}
        {!isUser && quickReplies.length > 0 && (
          <div className="bubble__quick-replies">
            {quickReplies.map((option) => (
              <button
                key={option}
                type="button"
                className="bubble__quick-reply"
                disabled={loading}
                onClick={() => onReply?.(option)}
              >
                {option}
              </button>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}