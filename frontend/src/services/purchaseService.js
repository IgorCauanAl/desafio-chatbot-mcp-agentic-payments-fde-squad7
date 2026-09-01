import { authHeader } from './authService';

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

export async function createIntention(productId, quantity) {
  const response = await fetch(`${API_URL}/api/v1/purchase-intentions`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...authHeader() },
    body: JSON.stringify({ product_id: productId, quantity }),
  });

  const body = await response.json();

  if (!response.ok) {
    throw new Error(body.error?.message || 'Erro ao registrar intenção.');
  }

  return body.data;
}

export async function createPurchase(intentionId, paymentMethod) {
  const response = await fetch(`${API_URL}/api/v1/purchases`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Idempotency-Key': crypto.randomUUID(),
      ...authHeader(),
    },
    body: JSON.stringify({ intention_id: intentionId, payment_method: paymentMethod }),
  });

  const body = await response.json();

  if (!response.ok) {
    throw new Error(body.error?.message || 'Erro ao realizar compra.');
  }

  return body.data;
}