const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

export async function loginRequest(email, password) {
  const response = await fetch(`${API_URL}/api/v1/auth/tokens`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email, password }),
  });

  const body = await response.json();

  if (!response.ok) {
    throw new Error(body.error?.message || 'Erro ao entrar.');
  }

  return body.data; // { access_token, token_type, expires_in }
}

export function authHeader() {
  const token = sessionStorage.getItem('auth_token');
  return token ? { Authorization: `Bearer ${token}` } : {};
}