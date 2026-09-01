import { useCallback, useEffect, useRef, useState } from 'react';

const CHAT_WS_PATH = '/api/v1/chat/ws';
const RECONNECT_BASE_DELAY = 1000;
const RECONNECT_MAX_DELAY = 10000;

export function useChat() {
  const [messages, setMessages] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const socketRef = useRef(null);
  const pendingAssistantRef = useRef(null);
  const reconnectTimerRef = useRef(null);
  const reconnectAttemptRef = useRef(0);
  const isUnmountedRef = useRef(false);
  const connectSocketRef = useRef(null);

  const connectSocket = useCallback(() => {
    if (isUnmountedRef.current) return null;

    const token = sessionStorage.getItem('auth_token');
    if (!token) {
      setError('Sessão expirada. Faça login novamente.');
      return null;
    }

    if (socketRef.current && [WebSocket.OPEN, WebSocket.CONNECTING].includes(socketRef.current.readyState)) {
      return socketRef.current;
    }

    const backendBase =
      import.meta.env.VITE_WS_URL ||
      import.meta.env.VITE_API_URL ||
      (window.location.hostname === 'localhost' ? 'http://localhost:8000' : window.location.origin);
    const wsBaseUrl = backendBase.replace(/^http/, 'ws').replace(/\/$/, '');
    const wsUrl = `${wsBaseUrl}${CHAT_WS_PATH}?token=${encodeURIComponent(token)}`;
    const socket = new WebSocket(wsUrl);
    socketRef.current = socket;

    socket.onopen = () => {
      reconnectAttemptRef.current = 0;
      setError('');
    };

    socket.onmessage = (event) => {
      let payload;

      try {
        payload = JSON.parse(event.data);
      } catch (error) {
        console.error('Mensagem inválida recebida pelo WebSocket do chat.', error);
        setError('Resposta inválida do chat. Tente novamente.');
        return;
      }

      if (!payload || typeof payload !== 'object') {
        return;
      }

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
      setLoading(false);
    };

    socket.onclose = () => {
      if (socketRef.current !== socket || isUnmountedRef.current) return;
      socketRef.current = null;
      setLoading(false);
      const delay = Math.min(
        RECONNECT_BASE_DELAY * 2 ** reconnectAttemptRef.current,
        RECONNECT_MAX_DELAY,
      );
      reconnectAttemptRef.current += 1;
      setError('Conexão do chat interrompida. Reconectando...');
      reconnectTimerRef.current = window.setTimeout(() => {
        reconnectTimerRef.current = null;
        connectSocketRef.current?.();
      }, delay);
    };

    return socket;
  }, []);

  useEffect(() => {
    isUnmountedRef.current = false;
    connectSocketRef.current = connectSocket;
    const initialConnectionTimer = window.setTimeout(() => {
      connectSocket();
    }, 0);

    return () => {
      isUnmountedRef.current = true;
      connectSocketRef.current = null;
      window.clearTimeout(initialConnectionTimer);
      if (reconnectTimerRef.current) {
        window.clearTimeout(reconnectTimerRef.current);
        reconnectTimerRef.current = null;
      }
      if (socketRef.current) {
        socketRef.current.close();
      }
      socketRef.current = null;
    };
  }, [connectSocket]);

  async function send(text) {
    const trimmed = text.trim();
    if (!trimmed) return;

    const socket = socketRef.current || connectSocket();
    if (!socket || socket.readyState !== WebSocket.OPEN) {
      setError('Conectando ao chat. Tente novamente em instantes.');
      return;
    }

    setMessages((prev) => [...prev, { role: 'user', content: trimmed, timestamp: new Date().toISOString() }]);
    setLoading(true);
    setError('');
    socket.send(JSON.stringify({ message: trimmed }));
  }

  return { messages, loading, error, send };
}