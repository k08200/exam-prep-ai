'use client';
import { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import Cookies from 'js-cookie';
import { authApi } from '@/lib/api';
import type { User } from '@/types';

const AUTH_REFRESH_EVENT = 'exam-prep-ai:auth-refresh';
const AUTH_LOGOUT_EVENT = 'exam-prep-ai:auth-logout';

export function useAuth() {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);
  const router = useRouter();

  useEffect(() => {
    const refreshFromServer = async () => {
      try {
        const res = await authApi.me();
        setUser(res.data);
      } catch {
        Cookies.remove('access_token');
        setUser(null);
      } finally {
        setLoading(false);
      }
    };

    const handleLogout = () => {
      setUser(null);
      setLoading(false);
    };

    window.addEventListener(AUTH_REFRESH_EVENT, refreshFromServer);
    window.addEventListener(AUTH_LOGOUT_EVENT, handleLogout);

    const token = Cookies.get('access_token');
    if (!token) {
      setLoading(false);
    } else {
      refreshFromServer();
    }

    return () => {
      window.removeEventListener(AUTH_REFRESH_EVENT, refreshFromServer);
      window.removeEventListener(AUTH_LOGOUT_EVENT, handleLogout);
    };
  }, []);

  const login = async (email: string, password: string) => {
    const res = await authApi.login(email, password);
    Cookies.set('access_token', res.data.access_token, { expires: 7 });
    const me = await authApi.me();
    setUser(me.data);
    window.dispatchEvent(new Event(AUTH_REFRESH_EVENT));
    router.push('/dashboard');
  };

  const logout = () => {
    Cookies.remove('access_token');
    setUser(null);
    window.dispatchEvent(new Event(AUTH_LOGOUT_EVENT));
    router.push('/auth/login');
  };

  const refreshUser = async () => {
    try {
      const res = await authApi.me();
      setUser(res.data);
      window.dispatchEvent(new Event(AUTH_REFRESH_EVENT));
    } catch {
      // ignore — token may have expired
    }
  };

  return { user, loading, login, logout, refreshUser };
}
