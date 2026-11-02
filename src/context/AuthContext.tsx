import React, { createContext, useContext, useState, useEffect, useCallback } from 'react';
import { User } from '../types';
import { api, getAuthToken, setAuthToken, removeAuthToken, setUnauthorizedHandler, RegisterInput } from '../api/client';

interface AuthContextType {
  user: User | null;
  isLoading: boolean;
  sessionNotice: string | null;
  login: (email: string, password: string) => Promise<void>;
  register: (data: RegisterInput) => Promise<void>;
  logout: () => void;
  refreshUser: () => Promise<void>;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export const AuthProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [user, setUser] = useState<User | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [sessionNotice, setSessionNotice] = useState<string | null>(null);

  const refreshUser = useCallback(async () => {
    if (!getAuthToken()) {
      setUser(null);
      setIsLoading(false);
      return;
    }
    try {
      setUser(await api.getMe());
    } catch (err: any) {
      // 401 is handled by the global handler; other failures also end the session cleanly.
      removeAuthToken();
      setUser(null);
      if (err?.status !== 401) setSessionNotice('Could not restore your session. Please sign in again.');
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    setUnauthorizedHandler(() => {
      setUser(null);
      setSessionNotice('Your session has expired or is no longer valid. Please sign in again.');
    });
    void refreshUser();
    return () => setUnauthorizedHandler(null);
  }, [refreshUser]);

  const login = async (email: string, password: string) => {
    const response = await api.login({ email, password });
    setAuthToken(response.access_token);
    setSessionNotice(null);
    setUser(response.user);
  };

  const register = async (data: RegisterInput) => {
    await api.register(data);
    await login(data.email, data.password);
  };

  const logout = () => {
    removeAuthToken();
    setSessionNotice(null);
    setUser(null);
    if (window.location.hash) window.location.hash = '';
  };

  return (
    <AuthContext.Provider value={{ user, isLoading, sessionNotice, login, register, logout, refreshUser }}>
      {children}
    </AuthContext.Provider>
  );
};

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) throw new Error('useAuth must be used within an AuthProvider');
  return context;
}
