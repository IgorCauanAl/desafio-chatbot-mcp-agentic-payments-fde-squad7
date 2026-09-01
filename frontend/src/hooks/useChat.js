import { useCallback, useEffect, useRef, useState } from 'react';

const CHAT_WS_PATH = '/api/v1/chat/ws';

export function useChat() {
  const [messages, setMessages] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const socketRef = useRef(null);
  const pendingAssistantRef = useRef(null);

  const connectSocket = useCallback(() => {
    const token = sessionStorage.getItem('auth_token');
    if (!token) {
      setError('Sessão expirada. Faça login novamente.');
      return null;
    }

    if (socketRef.current && [WebSocket.OPEN, WebSocket.CONNECTING].includes(socketRef.current.readyState)) {
      return socketRef.current;
    }

    const backendBase = import.meta.env.VITE_WS_URL || import.meta.env.VITE_API_URL || window.location.origin;
    const wsBaseUrl = backendBase.replace(/^http/, 'ws').replace(/\/$/, '');
    const wsUrl = `${wsBaseUrl}${CHAT_WS_PATH}?token=${encodeURIComponent(token)}`;
    const socket = new WebSocket(wsUrl);
    socketRef.current = socket;

    socket.onopen = () => {
      setError('');
    };

    socket.onmessage = (event) => {
      const payload = JSON.parse(event.data);

      if (payload.type === 'chunk') {
        const text = payload.content || '';
        if (!text) return;

        setMessages((prev) => {
          const next = [...prev];
          const last = next[next.length - 1];

          if (last && last.role === 'assistant' && last.pending) {
            next[next.length - 1] = { ...last, content: `${last.content}${text}`, pending: true };
            return next;
          }

          next.push({ role: 'assistant', content: text, pending: true, timestamp: new Date().toISOString() });
          return next;
        });
        pendingAssistantRef.current = true;
        return;
      }

      if (payload.type === 'done') {
        setMessages((prev) => prev.map((message, index) => {
          if (index === prev.length - 1 && message.role === 'assistant' && message.pending) {
            return { ...message, pending: false };
          }
          return message;
        }));
        pendingAssistantRef.current = false;
        setLoading(false);
        return;
      }

      if (payload.type === 'error') {
        setMessages((prev) => [...prev, {
          role: 'assistant',
          content: payload.message || 'Não foi possível processar esta mensagem.',
          pending: false,
          timestamp: new Date().toISOString(),
        }]);
        setLoading(false);
        setError(payload.message || 'Erro no chat.');
      }
    };

    socket.onerror = () => {
      setError('Não foi possível conectar ao chat. Tente novamente.');
      setLoading(false);
    };

    socket.onclose = () => {
      socketRef.current = null;
      if (pendingAssistantRef.current) {
        setLoading(false);
        setError('Conexão encerrada. Reabrindo a sessão...');
      } else {
        setError('Conexão do chat indisponível. Tente novamente.');
      }
    };

    return socket;
  }, []);

  useEffect(() => {
    const socket = connectSocket();

    return () => {
      if (socket) {
        socket.close();
      }
      socketRef.current = null;
    };
  }, [connectSocket]);

  async function send(text) {
    const trimmed = text.trim();
    if (!trimmed) return;

    const socket = socketRef.current || connectSocket();
    if (!socket || socket.readyState !== WebSocket.OPEN) {
      setError('Conexão do chat indisponível. Tente novamente.');
      return;
    }

    setMessages((prev) => [...prev, { role: 'user', content: trimmed, timestamp: new Date().toISOString() }]);
    setLoading(true);
    setError('');
    socket.send(JSON.stringify({ message: trimmed }));
  }

  return { messages, loading, error, send };
}