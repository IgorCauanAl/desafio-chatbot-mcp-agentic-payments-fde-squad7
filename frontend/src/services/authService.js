const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:3000';

// Para alternar entre o uso de mock para API real, alterar esta variável para false
const USE_MOCK = true;

export async function loginRequest(username, password) {
  if (USE_MOCK) {
    // Simula um delay de rede
    await new Promise((resolve) => setTimeout(resolve, 1000));
    // Simula uma resposta de login bem-sucedida
    return { token: 'mock-token', user: { id: 1, username } };
  }

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

  // Simula latência de rede e retorna sempre sucesso, exceto campos vazios
function mockLoginRequest(username, password) {
  return new Promise((resolve, reject) => {
    setTimeout(() => {
      if (!username || !password) {
        reject(new Error('Usuário ou senha inválidos.'));
        return;
      }

      resolve({
        token: 'mock-token-123',
        user: { id: 'u1', username, limite: 500 },
      });
    }, 500);
  });
}

}