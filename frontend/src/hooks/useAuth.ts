'use client';
import { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import Cookies from 'js-cookie';
import { authApi } from '@/lib/api';
import type { User } from '@/types';

export function useAuth() {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);
  const router = useRouter();

  useEffect(() => {
    const token = Cookies.get('access_token');
    if (!token) {
      setLoading(false);
      return;
    }
    authApi
      .me()
      .then((res) => setUser(res.data))
      .catch(() => Cookies.remove('access_token'))
      .finally(() => setLoading(false));
  }, []);

  const login = async (email: string, password: string) => {
    const res = await authApi.login(email, password);
    Cookies.set('access_token', res.data.access_token, { expires: 7 });
    const me = await authApi.me();
    setUser(me.data);
    router.push('/dashboard');
  };

  const logout = () => {
    Cookies.remove('access_token');
    setUser(null);
    router.push('/auth/login');
  };

  return { user, loading, login, logout };
}
