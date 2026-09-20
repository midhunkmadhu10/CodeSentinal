'use client';

import React from 'react';
import { BookOpen, LogOut, Settings, Sparkles, Terminal } from 'lucide-react';

export type NavSection = 'Analyze' | 'Knowledge' | 'Settings';

const nav: [React.ElementType, NavSection][] = [
  [Terminal, 'Analyze'],
  [BookOpen, 'Knowledge'],
  [Settings, 'Settings'],
];

interface AnalyzeHeaderProps {
  activeNav: NavSection;
  onNavChange: (section: NavSection) => void;
  apiOnline: boolean | null;
  onLogout: () => void;
}

export default function AnalyzeHeader({ activeNav, onNavChange, apiOnline, onLogout }: AnalyzeHeaderProps) {
  return (
    <nav className="fixed top-3 sm:top-6 left-1/2 -translate-x-1/2 z-50 w-[calc(100%-1rem)] sm:w-[calc(100%-3rem)] max-w-5xl">
      <div className="glass-panel rounded-2xl sm:rounded-full px-3 sm:px-6 py-3 flex flex-wrap items-center justify-between gap-x-3 gap-y-2 sm:flex-nowrap">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-full bg-foreground flex items-center justify-center">
            <Sparkles className="w-4 h-4 text-background" strokeWidth={2} />
          </div>
          <span className="hidden sm:inline font-semibold tracking-tight text-[15px]">CodeSentinal</span>
        </div>

        <div className="order-3 flex w-full items-center justify-center gap-1 sm:order-none sm:w-auto sm:gap-2">
          {nav.map(([Icon, name]) => (
            <button
              key={name}
              onClick={() => onNavChange(name)}
              className={`flex items-center gap-1.5 px-3 sm:px-4 py-2 rounded-full text-[12px] sm:text-[13px] font-medium transition-all duration-300 ${activeNav === name ? 'bg-white/10 text-foreground' : 'text-foreground-muted hover:text-foreground hover:bg-white/5'}`}
            >
              {activeNav === name && <Icon className="w-4 h-4" />}
              {name}
            </button>
          ))}
        </div>

        <div className="flex items-center gap-2 sm:gap-4">
          <div className="flex items-center gap-2 text-[11px] sm:text-[12px] text-foreground-muted whitespace-nowrap">
            <span className={`w-2 h-2 rounded-full ${apiOnline ? 'bg-success shadow-[0_0_10px_rgba(34,197,94,0.5)]' : 'bg-danger'}`}></span>
            {apiOnline ? 'System Online' : 'Offline'}
          </div>
          <div className="w-px h-4 bg-border"></div>
          <button onClick={onLogout} aria-label="Log out" className="text-foreground-muted hover:text-foreground transition-colors">
            <LogOut className="w-4 h-4" />
          </button>
        </div>
      </div>
    </nav>
  );
}
