import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../../hooks/useAuth';
import Alert from '../Alert';
import './loginForm.css';

export default function LoginForm() {
  const { login, loading, error } = useAuth();
  const navigate = useNavigate();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');

  async function handleSubmit(e) {
    e.preventDefault();
    const ok = await login(email, password);
    if (ok) navigate('/chat');
  }

  return (
    <form className="ticket-form" onSubmit={handleSubmit}>
      <div className="ticket-header">
        <span className="ticket-eyebrow">entrada · sessão nova</span>
        <h1 className="ticket-title">Entrar</h1>
      </div>

      <div className="ticket-field">
        <label htmlFor="email">e-mail</label>
        <input
          id="email"
          type="email"
          autoComplete="email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
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

      {error && <Alert type="error" message={error} />}

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