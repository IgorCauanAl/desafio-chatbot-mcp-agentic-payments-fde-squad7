import { authHeader } from './authService';

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

export async function listProducts(category) {
  const params = new URLSearchParams();
  if (category) params.set('category', category);

  const response = await fetch(`${API_URL}/api/v1/products?${params}`, {
    headers: { ...authHeader() },
  });

  const body = await response.json();

  if (!response.ok) {
    throw new Error(body.error?.message || 'Erro ao buscar catálogo.');
  }

  return body.data; // array de produtos
}