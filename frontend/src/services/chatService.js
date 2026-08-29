const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:3000';
const USE_MOCK = true;

const catalogo = [
  { id: 'prod_001', nome: 'Teclado Mecânico', preco: 189.9, moeda: 'BRL', estoque: 8 },
  { id: 'prod_002', nome: 'Mouse Gamer', preco: 99.9, moeda: 'BRL', estoque: 15 },
  { id: 'prod_003', nome: 'Fone Bluetooth', preco: 249.9, moeda: 'BRL', estoque: 12 },
];

export async function sendMessage(text, history) {
  if (USE_MOCK) return mockSendMessage(text);

  const response = await fetch(`${API_URL}/api/chat`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${sessionStorage.getItem('auth_token')}`,
    },
    body: JSON.stringify({ message: text, history }),
  });

  if (!response.ok) throw new Error('Erro ao falar com o agente.');
  return response.json(); // { reply, toolCall? }
}

function mockSendMessage(text) {
  return new Promise((resolve) => {
    setTimeout(() => {
      const lower = text.toLowerCase();

      if (lower.includes('vend') || lower.includes('catálogo') || lower.includes('catalogo')) {
        resolve({
          reply: 'Aqui está o que temos disponível:',
          toolCall: { name: 'listar_catalogo', args: {}, result: { produtos: catalogo } },
        });
        return;
      }

      if (lower.includes('item 3') || lower.includes('fone')) {
        resolve({
          reply: 'Registrei sua intenção de compra. Quer pagar no pix ou cartão?',
          toolCall: {
            name: 'registrar_intencao',
            args: { produto_id: 'prod_003', quantidade: 1 },
            result: {
              intencao_id: 'int_a1b2c3',
              produto_id: 'prod_003',
              quantidade: 1,
              valor_total: 249.9,
              moeda: 'BRL',
              status: 'pendente',
              expira_em: new Date(Date.now() + 10 * 60 * 1000).toISOString(),
            },
          },
        });
        return;
      }

      if (lower.includes('pix') || lower.includes('cartão') || lower.includes('cartao')) {
        const metodo = lower.includes('pix') ? 'pix' : 'cartao';
        resolve({
          reply: 'Compra aprovada! 🎉',
          toolCall: {
            name: 'realizar_compra',
            args: { intencao_id: 'int_a1b2c3', metodo_pagamento: metodo },
            result: {
              status: 'aprovado',
              transacao_id: 'tx_9f8e7d',
              intencao_id: 'int_a1b2c3',
              valor: 249.9,
              metodo_pagamento: metodo,
              limite_restante: 250.1,
              data: new Date().toISOString(),
            },
          },
        });
        return;
      }

      resolve({ reply: 'Posso te mostrar o catálogo ou registrar uma compra. O que você precisa?' });
    }, 700);
  });
}