import { createContext, useState, useCallback } from 'react';
import { loginRequest } from '../services/authService';

export const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [token, setToken] = useState(() => sessionStorage.getItem('auth_token'));
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(false);

  const login = useCallback(async (email, password) => {
    setLoading(true);
    setError(null);
    try {
      const { access_token } = await loginRequest(email, password);
      sessionStorage.setItem('auth_token', access_token);
      setToken(access_token);
      return true;
    } catch (err) {
      setError(err.message || 'Não foi possível entrar.');
      return false;
    } finally {
      setLoading(false);
    }
  }, []);

  const logout = useCallback(() => {
    sessionStorage.removeItem('auth_token');
    setToken(null);
  }, []);

  const value = { token, isAuthenticated: Boolean(token), login, logout, error, loading };

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}