import ToolCallCard from './ToolCallCard.jsx';
import './messageBubble.css';

export default function MessageBubble({ message }) {
  const isUser = message.role === 'user';

  return (
    <div className={`bubble-row ${isUser ? 'bubble-row--user' : ''}`}>
      <div className={`bubble ${isUser ? 'bubble--user' : 'bubble--agent'}`}>
        <p>{message.content}</p>
        {message.toolCall && <ToolCallCard toolCall={message.toolCall} />}
      </div>
    </div>
  );
}