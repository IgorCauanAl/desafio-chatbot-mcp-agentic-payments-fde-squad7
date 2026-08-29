import './toolCallCard.css';

export default function ToolCallCard({ toolCall }) {
  const { name, result } = toolCall;

  return (
    <div className="tool-card">
      <span className="tool-card__name">{name}</span>
      <div className="tool-card__body">
        {Object.entries(flatten(result)).map(([key, value]) => (
          <div key={key} className="tool-card__row">
            <span>{key}</span>
            <span>{String(value)}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

function flatten(obj) {
  if (!obj || typeof obj !== 'object') return {};
  if (Array.isArray(obj.produtos)) {
    return { produtos: `${obj.produtos.length} itens` };
  }
  return obj;
}