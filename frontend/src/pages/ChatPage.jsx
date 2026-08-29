import { useChat } from '../hooks/useChat';
import MessageList from '../components/chat/MessageList';
import ChatInput from '../components/chat/ChatInput';
import './chatPage.css';

export default function ChatPage() {
  const { messages, loading, send } = useChat();

   return (
    <div className="chat-page">
      <header className="chat-header">
        <span className="chat-header__eyebrow">sessão ativa</span>
        <h1 className="chat-header__title">Assistente de Compras</h1>
      </header>
      <MessageList messages={messages} />
      <ChatInput onSend={send} disabled={loading} />
    </div>
  );
}