import './toolCallCard.css';

const LABELS = {
  intention_id: 'intencao_id',
  product_id: 'produto_id',
  quantity: 'quantidade',
  total_amount: 'valor_total',
  currency: 'moeda',
  status: 'status',
  expires_at: 'expira_em',
  transaction_id: 'transacao_id',
  amount: 'valor',
  payment_method: 'metodo_pagamento',
  remaining_limit: 'limite_restante',
  date: 'data',
};

export default function ToolCallCard({ toolCall }) {
  const { name, result } = toolCall;

  if (name === 'listar_catalogo' && Array.isArray(result?.produtos)) {
    return (
      <div className="tool-card">
        <span className="tool-card__name">{name}</span>
        <div className="tool-card__list">
          {result.produtos.map((p) => (
            <div key={p.id} className="tool-card__product">
              <span className="tool-card__product-id">{p.id}</span>
              <span>{p.name}</span>
              <span>R$ {Number(p.price).toFixed(2)}</span>
            </div>
          ))}
        </div>
      </div>
    );
  }

  return (
    <div className="tool-card">
      <span className="tool-card__name">{name}</span>
      <div className="tool-card__body">
        {Object.entries(result || {}).map(([key, value]) => (
          <div key={key} className="tool-card__row">
            <span>{LABELS[key] || key}</span>
            <span>{String(value)}</span>
          </div>
        ))}
      </div>
    </div>
  );
}