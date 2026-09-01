import { useState } from 'react';
import './ChatInput.css';

export default function ChatInput({ onSend, disabled }) {
  const [text, setText] = useState('');

  function handleSubmit(e) {
    e?.preventDefault?.();
    if (!text.trim()) return;
    onSend(text);
    setText('');
  }

  function handleKeyDown(e) {
    if (e.key === 'Enter') {
      handleSubmit(e);
    }
  }

  return (
    <form className="chat-input" onSubmit={handleSubmit}>
      <input
        type="text"
        placeholder="Digite sua mensagem..."
        value={text}
        onChange={(e) => setText(e.target.value)}
        onKeyDown={handleKeyDown}
        disabled={disabled}
      />
      <button type="submit" disabled={disabled}>Enviar</button>
    </form>
  );
}