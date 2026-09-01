import './toolCallCard.css';

const LABELS = {
  intention_id: 'identificador',
  product_id: 'produto',
  quantity: 'quantidade',
  total_amount: 'valor total',
  currency: 'moeda',
  status: 'status',
  expires_at: 'expira em',
  transaction_id: 'transação',
  amount: 'valor',
  payment_method: 'pagamento',
  remaining_limit: 'saldo restante',
  date: 'data',
};

function formatMoney(value) {
  const numeric = Number(value ?? 0);
  return new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL' }).format(numeric);
}

function renderFriendlySummary(result = {}) {
  const entries = Object.entries(result).filter(([key, value]) => value !== undefined && value !== null && value !== '');

  if (!entries.length) {
    return <div className="tool-card__empty">Sem detalhes para mostrar.</div>;
  }

  return (
    <div className="tool-card__body">
      {entries.map(([key, value]) => {
        const label = LABELS[key] || key.replace(/_/g, ' ');
        let display = String(value);

        if (key === 'amount' || key === 'total_amount' || key === 'remaining_limit') {
          display = formatMoney(value);
        }

        if (key === 'payment_method') {
          display = value === 'cartao' ? 'Cartão' : value === 'pix' ? 'Pix' : display;
        }

        if (key === 'status') {
          display = value === 'aprovado' ? 'Confirmado' : value === 'pendente' ? 'Pendente' : display;
        }

        return (
          <div key={key} className="tool-card__row">
            <span>{label}</span>
            <strong>{display}</strong>
          </div>
        );
      })}
    </div>
  );
}

export default function ToolCallCard({ toolCall }) {
  const { name, result } = toolCall;

  if (name === 'listar_catalogo' && Array.isArray(result?.produtos)) {
    return (
      <div className="tool-card tool-card--catalog">
        <span className="tool-card__name">catálogo</span>
        <div className="tool-card__list">
          {result.produtos.map((p) => (
            <div key={p.id} className="tool-card__product">
              <div className="tool-card__product-badge">{p.category || 'Produto'}</div>
              <div className="tool-card__product-name">{p.name}</div>
              <div className="tool-card__product-meta">
                <span>{p.stock} em estoque</span>
                <strong>{formatMoney(p.price)}</strong>
              </div>
            </div>
          ))}
        </div>
      </div>
    );
  }

  return (
    <div className="tool-card">
      <span className="tool-card__name">{name.replace(/_/g, ' ')}</span>
      {renderFriendlySummary(result)}
    </div>
  );
}