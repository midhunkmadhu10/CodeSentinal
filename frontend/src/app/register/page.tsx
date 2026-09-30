'use client';

import React, { useState } from 'react';
import { useRouter } from 'next/navigation';
import { useAuth } from '@/lib/auth';
import { register as apiRegister } from '@/lib/api';
import { Mail, Lock, User, AlertCircle, ArrowRight, Sparkles } from 'lucide-react';

export default function RegisterPage() {
  const { login, isAuthenticated } = useAuth();
  const router = useRouter();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [name, setName] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  // If already authenticated, redirect
  React.useEffect(() => {
    if (isAuthenticated) {
      router.replace('/dashboard');
    }
  }, [isAuthenticated, router]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');

    if (!email.trim() || !password.trim()) {
      setError('Please enter both email and password.');
      return;
    }

    if (password.length < 8) {
      setError('Password must be at least 8 characters.');
      return;
    }

    setLoading(true);
    try {
      const data = await apiRegister(email, password, name);
      login(data.access_token);
      router.replace('/dashboard');
    } catch (err: any) {
      setError(err.message || 'Registration failed. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-background relative overflow-hidden">
      {/* Ambient Lighting */}
      <div className="ambient-glow bg-primary w-[500px] h-[500px] -top-[200px] -right-[200px]"></div>
      <div className="ambient-glow bg-accent w-[600px] h-[600px] -bottom-[300px] -left-[200px] opacity-10"></div>
      
      <div className="w-full max-w-[400px] z-10 animate-fade-in px-6">
        <div className="text-center mb-12">
          <div className="inline-flex items-center justify-center mb-6">
            <Sparkles className="w-10 h-10 text-foreground" strokeWidth={1.5} />
          </div>
          <h1 className="text-3xl font-medium tracking-tight text-foreground mb-2">CodeSentinal</h1>
          <p className="text-foreground-muted font-light text-[15px]">Create your account</p>
        </div>

        <form onSubmit={handleSubmit} className="glass-panel rounded-2xl p-8 space-y-6 animate-slide-up">
          {error && (
            <div className="flex items-start gap-3 p-4 rounded-xl bg-danger/10 border border-danger/20 text-sm text-danger animate-fade-in">
              <AlertCircle className="w-4 h-4 mt-0.5 shrink-0" />
              <span>{error}</span>
            </div>
          )}

          <div className="space-y-5">
            <div className="group relative">
              <User className="absolute left-0 top-1/2 -translate-y-1/2 w-5 h-5 text-foreground-muted/50" />
              <input
                id="name"
                type="text"
                value={name}
                onChange={(e) => setName(e.target.value)}
                className="w-full pl-10 pr-0 py-3 bg-transparent border-b border-border text-foreground placeholder:text-foreground-muted focus:outline-none focus:border-primary transition-all duration-300 font-light text-[15px]"
                placeholder="Name (optional)"
                autoComplete="name"
                disabled={loading}
              />
            </div>

            <div className="group relative">
              <Mail className="absolute left-0 top-1/2 -translate-y-1/2 w-5 h-5 text-foreground-muted/50" />
              <input
                id="email"
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                className="w-full pl-10 pr-0 py-3 bg-transparent border-b border-border text-foreground placeholder:text-foreground-muted focus:outline-none focus:border-primary transition-all duration-300 font-light text-[15px]"
                placeholder="Email"
                autoComplete="email"
                disabled={loading}
              />
            </div>

            <div className="group relative">
              <Lock className="absolute left-0 top-1/2 -translate-y-1/2 w-5 h-5 text-foreground-muted/50" />
              <input
                id="password"
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="w-full pl-10 pr-0 py-3 bg-transparent border-b border-border text-foreground placeholder:text-foreground-muted focus:outline-none focus:border-primary transition-all duration-300 font-light text-[15px]"
                placeholder="Password (min 8 characters)"
                autoComplete="new-password"
                disabled={loading}
              />
            </div>
          </div>

          <button
            type="submit"
            disabled={loading}
            className="w-full flex items-center justify-between px-6 py-3.5 mt-8 bg-foreground hover:bg-white text-background font-medium rounded-xl transition-all duration-300 active:scale-[0.98] disabled:opacity-50 disabled:cursor-not-allowed group shadow-premium hover:shadow-premium-hover"
          >
            <span className="text-[15px]">Create Account</span>
            {loading ? (
              <span className="w-4 h-4 border-2 border-background/30 border-t-background rounded-full animate-spin" />
            ) : (
              <ArrowRight className="w-4 h-4 transition-transform duration-300 group-hover:translate-x-1" />
            )}
          </button>
        </form>

        <p className="text-center text-[13px] text-foreground-muted mt-8 font-light animate-fade-in" style={{ animationDelay: '0.2s' }}>
          Already have an account?{' '}
          <a href="/" className="text-primary hover:underline font-medium">
            Sign in
          </a>
        </p>
      </div>
    </div>
  );
}