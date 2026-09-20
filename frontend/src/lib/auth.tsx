'use client';

import React, { createContext, useContext, useState, useEffect, useCallback } from 'react';
import { clearToken, getToken, storeToken } from './api';

interface AuthContextType {
  token: string | null;
  login: (token: string) => void;
  logout: () => void;
  isAuthenticated: boolean;
}

const AuthContext = createContext<AuthContextType>({
  token: null,
  login: () => {},
  logout: () => {},
  isAuthenticated: false,
});

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [token, setToken] = useState<string | null>(null);

  useEffect(() => {
    const stored = getToken();
    if (stored) {
      setToken(stored);
    }
  }, []);

  const login = useCallback((newToken: string) => {
    storeToken(newToken);
    setToken(newToken);
  }, []);

  const logout = useCallback(() => {
    clearToken();
    setToken(null);
  }, []);

  return (
    <AuthContext.Provider value={{ token, login, logout, isAuthenticated: !!token }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  return useContext(AuthContext);
}
