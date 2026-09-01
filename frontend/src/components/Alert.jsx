import './alert.css';

export default function Alert({ type = 'error', message }) {
  if (!message) return null;

  return (
    <div className={`alert alert--${type}`} role="alert">
      <span className="alert__icon">{type === 'success' ? '✓' : '!'}</span>
      <span>{message}</span>
    </div>
  );
}