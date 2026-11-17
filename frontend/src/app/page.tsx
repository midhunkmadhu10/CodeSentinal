'use client';

import React, { useState } from 'react';
import { useRouter } from 'next/navigation';
import { useAuth } from '@/lib/auth';
import { login as apiLogin, loginWithEmail } from '@/lib/api';
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
      // Prefer the multi-user JWT endpoint (email + password) and fall back to
      // the legacy shared-credential login so existing deployments keep working.
      let token: string;
      try {
        const result = await loginWithEmail(username, password);
        token = result.access_token;
      } catch {
        token = await apiLogin(username, password);
      }
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