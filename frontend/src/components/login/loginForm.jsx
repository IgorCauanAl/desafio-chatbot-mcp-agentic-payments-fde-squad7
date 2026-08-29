import { useState } from 'react';
import { useAuth } from '../../hooks/useAuth';
import './LoginForm.css';
import { useNavigate } from 'react-router-dom';

export default function LoginForm() {
  const { login, loading, error } = useAuth();
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const navigate = useNavigate();

  async function handleSubmit(e) {
    e.preventDefault();
    const ok = await login(username, password);
    if (ok) {
      navigate('/chat');
    }
  }

  return (
    <form className="ticket-form" onSubmit={handleSubmit}>
      <div className="ticket-header">
        <span className="ticket-eyebrow">entrada · sessão nova</span>
        <h1 className="ticket-title">Entrar</h1>
      </div>

      <div className="ticket-field">
        <label htmlFor="username">usuário</label>
        <input
          id="username"
          type="text"
          autoComplete="username"
          value={username}
          onChange={(e) => setUsername(e.target.value)}
          required
        />
      </div>

      <div className="ticket-field">
        <label htmlFor="password">senha</label>
        <input
          id="password"
          type="password"
          autoComplete="current-password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          required
        />
      </div>

      {error && <p className="ticket-error" role="alert">{error}</p>}

      <button className="ticket-submit" type="submit" disabled={loading}>
        {loading ? 'verificando…' : 'entrar no chat'}
      </button>

      <div className="ticket-barcode" aria-hidden="true">
        {Array.from({ length: 28 }).map((_, i) => (
          <span key={i} style={{ width: i % 3 === 0 ? '3px' : '1px' }} />
        ))}
      </div>
    </form>
  );
}