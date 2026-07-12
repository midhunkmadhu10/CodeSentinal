'use client';

import React, { useState } from 'react';
import { useRouter } from 'next/navigation';
import { useAuth } from '@/lib/auth';
import { login as apiLogin } from '@/lib/api';
import LoginForm from '@/components/LoginForm';

export default function Home() {
  const { login, isAuthenticated } = useAuth();
  const router = useRouter();
  const [loading, setLoading] = useState(false);

  // If already authenticated, redirect
  React.useEffect(() => {
    if (isAuthenticated) {
      router.replace('/analyze');
    }
  }, [isAuthenticated, router]);

  const handleLogin = async (username: string, password: string) => {
    setLoading(true);
    try {
      const token = await apiLogin(username, password);
      login(token);
      router.replace('/analyze');
    } finally {
      setLoading(false);
    }
  };

  if (isAuthenticated) {
    return null; // Will redirect
  }

  return <LoginForm onLogin={handleLogin} />;
}