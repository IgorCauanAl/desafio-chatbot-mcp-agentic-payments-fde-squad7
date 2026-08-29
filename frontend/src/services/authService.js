const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:3000';

export async function loginRequest(username, password) {
  const response = await fetch(`${API_URL}/api/auth/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ username, password }),
  });

  if (!response.ok) {
    if (response.status === 401) {
      throw new Error('Usuário ou senha inválidos.');
    }
    throw new Error('Erro ao conectar com o servidor.');
  }

  return response.json(); // esperado: { token, user }
}