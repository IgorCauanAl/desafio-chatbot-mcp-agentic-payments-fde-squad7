import { listProducts } from './productService';
import { createIntention, createPurchase } from './purchaseService';

const CONFIRMATION_KEYWORDS = ['sim', 'confirmo', 'confirmar', 'pode prosseguir', 'prosseguir', 'ok'];

export async function sendMessage(text, history) {
  const lower = text.toLowerCase();

  if (lower.includes('vend') || lower.includes('catálogo') || lower.includes('catalogo')) {
    return handleListCatalog();
  }

  const pendingProduct = findPendingProduct(history);
  if (pendingProduct) {
    const quantidade = extractQuantity(lower);
    if (!quantidade) {
      return { reply: 'Não entendi a quantidade. Quantas unidades você quer?' };
    }
    return handleIntention(pendingProduct, quantidade);
  }

  const pendingPurchase = findPendingPurchase(history);
  if (pendingPurchase) {
    if (CONFIRMATION_KEYWORDS.some((keyword) => lower.includes(keyword))) {
      return handlePurchase(pendingPurchase.intencao_id, pendingPurchase.metodo_pagamento);
    }

    if (lower.includes('pix') || lower.includes('cartão') || lower.includes('cartao')) {
      const metodo = lower.includes('pix') ? 'pix' : 'cartao';
      return askForConfirmation(pendingPurchase.intencao_id, metodo, pendingPurchase.total_amount);
    }
  }

  const lastIntention = findLastIntention(history);
  if (lower.includes('pix') || lower.includes('cartão') || lower.includes('cartao')) {
    const metodo = lower.includes('pix') ? 'pix' : 'cartao';
    return askForConfirmation(lastIntention?.intention_id, metodo, lastIntention?.total_amount);
  }

  const produtoId = extractProductId(lower);
  if (produtoId) {
    return {
      reply: `Quantas unidades de ${produtoId} você quer?`,
      toolCall: { name: 'aguardando_quantidade', args: {}, result: { produto_id: produtoId } },
    };
  }

  return { reply: 'Posso te mostrar o catálogo ou registrar uma compra. O que você precisa?' };
}

async function handleListCatalog() {
  try {
    const produtos = await listProducts();
    return {
      reply: 'Aqui está o que temos disponível:',
      toolCall: { name: 'listar_catalogo', args: {}, result: { produtos } },
    };
  } catch (err) {
    return { reply: `Não consegui buscar o catálogo: ${err.message}` };
  }
}

async function handleIntention(productId, quantity) {
  try {
    const result = await createIntention(productId, quantity);
    return {
      reply: 'Registrei sua intenção de compra. Escolha o método de pagamento e confirme a compra para finalizar.',
      toolCall: { name: 'registrar_intencao', args: { produto_id: productId, quantidade: quantity }, result },
    };
  } catch (err) {
    return { reply: `Não consegui registrar a intenção: ${err.message}` };
  }
}

function askForConfirmation(intentionId, metodo, totalAmount) {
  if (!intentionId) {
    return { reply: 'Não encontrei uma intenção de compra ativa. Me diga qual produto você quer primeiro.' };
  }

  const formattedAmount = Number(totalAmount ?? 0).toLocaleString('pt-BR', {
    style: 'currency',
    currency: 'BRL',
  });

  return {
    reply: `Tudo certo. O total é ${formattedAmount} no ${metodo === 'pix' ? 'Pix' : 'Cartão'}. Confirme para finalizar o pagamento.`,
    toolCall: {
      name: 'aguardando_confirmacao',
      args: { intencao_id: intentionId, metodo_pagamento: metodo },
      result: {
        intencao_id: intentionId,
        metodo_pagamento: metodo,
        total_amount: totalAmount,
        status: 'pendente',
      },
    },
  };
}

async function handlePurchase(intentionId, metodo) {
  if (!intentionId) {
    return { reply: 'Não encontrei uma intenção de compra ativa. Me diga qual produto você quer primeiro.' };
  }

  try {
    const result = await createPurchase(intentionId, metodo);
    return {
      reply: 'Compra aprovada! 🎉 O valor foi descontado do seu saldo.',
      toolCall: { name: 'realizar_compra', args: { intencao_id: intentionId, metodo_pagamento: metodo, confirmado: true }, result },
    };
  } catch (err) {
    return {
      reply: `Não foi possível concluir a compra: ${err.message}`,
      toolCall: { name: 'realizar_compra', args: { intencao_id: intentionId, metodo_pagamento: metodo, confirmado: true }, result: { status: 'recusado', mensagem: err.message } },
    };
  }
}

function findPendingProduct(history) {
  for (let i = history.length - 1; i >= 0; i--) {
    const call = history[i]?.toolCall;
    if (call?.name === 'registrar_intencao') return null;
    if (call?.name === 'aguardando_quantidade') return call.result.produto_id;
  }
  return null;
}

function findPendingPurchase(history) {
  for (let i = history.length - 1; i >= 0; i--) {
    const call = history[i]?.toolCall;
    if (call?.name === 'aguardando_confirmacao') return call.result;
  }
  return null;
}

function findLastIntention(history) {
  for (let i = history.length - 1; i >= 0; i--) {
    const call = history[i]?.toolCall;
    if (call?.name === 'registrar_intencao') return call.result;
  }
  return null;
}

function extractQuantity(text) {
  const match = text.match(/\d+/);
  return match ? parseInt(match[0], 10) : null;
}

function extractProductId(text) {
  const match = text.match(/prod_\d+/);
  if (match) return match[0];
  if (text.includes('item 1')) return 'prod_001';
  if (text.includes('item 2')) return 'prod_002';
  if (text.includes('item 3')) return 'prod_003';
  return null;
}
