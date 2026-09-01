import { useState } from 'react';
import { sendMessage } from '../services/chatService';

export function useChat() {
  const [messages, setMessages] = useState([]);
  const [loading, setLoading] = useState(false);

  async function send(text) {
    const userMessage = { role: 'user', content: text, timestamp: new Date().toISOString() };
    const history = [...messages, userMessage];
    setMessages(history);
    setLoading(true);

    try {
      const { reply, toolCall } = await sendMessage(text, history);
      const agentMessage = {
        role: 'assistant',
        content: reply,
        toolCall,
        timestamp: new Date().toISOString(),
      };
      setMessages((prev) => [...prev, agentMessage]);
    } catch (err) {
      const errorMessage = {
        role: 'assistant',
        content: 'Algo deu errado. Tenta de novo?',
        timestamp: new Date().toISOString(),
      };
      setMessages((prev) => [...prev, errorMessage]);
    } finally {
      setLoading(false);
    }
  }

  return { messages, loading, send };
}