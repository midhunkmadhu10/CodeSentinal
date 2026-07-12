'use client';

import React from 'react';
import { Beaker } from 'lucide-react';

interface DemoButtonProps {
  onLoad: () => void;
  loading?: boolean;
}

export default function DemoButton({ onLoad, loading }: DemoButtonProps) {
  return (
    <button
      type="button"
      onClick={onLoad}
      disabled={loading}
      className="flex items-center gap-2 px-4 py-2 text-sm font-medium text-primary bg-primary/10 border border-primary/20 rounded-lg hover:bg-primary/15 transition-all duration-150 active:scale-[0.97] disabled:opacity-50 disabled:cursor-not-allowed"
    >
      <Beaker className="w-4 h-4" />
      {loading ? 'Loading demo...' : 'Load Demo'}
    </button>
  );
}