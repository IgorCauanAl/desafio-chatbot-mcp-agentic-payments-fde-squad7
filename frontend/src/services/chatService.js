import { listProducts } from './productService';
import { createIntention, createPurchase } from './purchaseService';

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

  const lastIntention = findLastIntention(history);
  if (lower.includes('pix') || lower.includes('cartão') || lower.includes('cartao')) {
    const metodo = lower.includes('pix') ? 'pix' : 'cartao';
    return handlePurchase(lastIntention?.intention_id, metodo);
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
      reply: 'Registrei sua intenção de compra. Quer pagar no pix ou cartão?',
      toolCall: { name: 'registrar_intencao', args: { produto_id: productId, quantidade: quantity }, result },
    };
  } catch (err) {
    return { reply: `Não consegui registrar a intenção: ${err.message}` };
  }
}

async function handlePurchase(intentionId, metodo) {
  if (!intentionId) {
    return { reply: 'Não encontrei uma intenção de compra ativa. Me diga qual produto você quer primeiro.' };
  }

  try {
    const result = await createPurchase(intentionId, metodo);
    return {
      reply: 'Compra aprovada! 🎉',
      toolCall: { name: 'realizar_compra', args: { intencao_id: intentionId, metodo_pagamento: metodo }, result },
    };
  } catch (err) {
    return {
      reply: `Não foi possível concluir a compra: ${err.message}`,
      toolCall: { name: 'realizar_compra', args: { intencao_id: intentionId, metodo_pagamento: metodo }, result: { status: 'recusado', mensagem: err.message } },
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
