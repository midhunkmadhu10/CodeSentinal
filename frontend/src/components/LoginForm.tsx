'use client';

import React, { useState } from 'react';
import { Sparkles, AlertCircle, ArrowRight } from 'lucide-react';

interface LoginFormProps {
  onLogin: (username: string, password: string) => Promise<void>;
}

export default function LoginForm({ onLogin }: LoginFormProps) {
  const [username, setUsername] = useState('admin');
  const [password, setPassword] = useState('homie');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');

    if (!username.trim() || !password.trim()) {
      setError('Please enter both username and password.');
      return;
    }

    setLoading(true);
    try {
      await onLogin(username, password);
    } catch (err: any) {
      setError(err.message || 'Login failed. Please check your credentials.');
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
          <p className="text-foreground-muted font-light text-[15px]">AI Precision Security</p>
        </div>

        <form onSubmit={handleSubmit} className="glass-panel rounded-2xl p-8 space-y-6 animate-slide-up">
          {error && (
            <div className="flex items-start gap-3 p-4 rounded-xl bg-danger/10 border border-danger/20 text-sm text-danger animate-fade-in">
              <AlertCircle className="w-4 h-4 mt-0.5 shrink-0" />
              <span>{error}</span>
            </div>
          )}

          <div className="space-y-5">
            <div className="group">
              <input
                id="username"
                type="text"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                className="w-full px-0 py-3 bg-transparent border-b border-border text-foreground placeholder:text-foreground-muted focus:outline-none focus:border-primary transition-all duration-300 font-light text-[15px]"
                placeholder="Username"
                autoComplete="username"
                disabled={loading}
              />
            </div>

            <div className="group">
              <input
                id="password"
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="w-full px-0 py-3 bg-transparent border-b border-border text-foreground placeholder:text-foreground-muted focus:outline-none focus:border-primary transition-all duration-300 font-light text-[15px]"
                placeholder="Password"
                autoComplete="current-password"
                disabled={loading}
              />
            </div>
          </div>

          <button
            type="submit"
            disabled={loading}
            className="w-full flex items-center justify-between px-6 py-3.5 mt-8 bg-foreground hover:bg-white text-background font-medium rounded-xl transition-all duration-300 active:scale-[0.98] disabled:opacity-50 disabled:cursor-not-allowed group shadow-premium hover:shadow-premium-hover"
          >
            <span className="text-[15px]">Sign In</span>
            {loading ? (
              <span className="w-4 h-4 border-2 border-background/30 border-t-background rounded-full animate-spin" />
            ) : (
              <ArrowRight className="w-4 h-4 transition-transform duration-300 group-hover:translate-x-1" />
            )}
          </button>
        </form>

        <p className="text-center text-[13px] text-foreground-muted mt-8 font-light animate-fade-in" style={{ animationDelay: '0.2s' }}>
          Secure access via CodeSentinal core.
        </p>
      </div>
    </div>
  );
}