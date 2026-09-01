import { useEffect, useRef } from 'react';
import MessageBubble from './MessageBubble';
import './messageList.css';

export default function MessageList({ messages, onReply, loading }) {
  const endRef = useRef(null);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  return (
    <div className="message-list">
      {messages.map((msg, i) => (
        <MessageBubble key={i} message={msg} onReply={onReply} loading={loading} />
      ))}
      <div ref={endRef} />
    </div>
  );
}