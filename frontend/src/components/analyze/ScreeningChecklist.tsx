'use client';

import React from 'react';
import { ShieldCheck } from 'lucide-react';

interface ScreeningSuggestion {
  priority: string;
  title: string;
  action: string;
}

interface ScreeningChecklistProps {
  suggestions: ScreeningSuggestion[];
}

export default function ScreeningChecklist({ suggestions }: ScreeningChecklistProps) {
  if (suggestions.length === 0) return null;

  return (
    <section className="scroll-mt-32 animate-slide-up" id="screening">
      <div className="flex items-center gap-3 mb-5">
        <div className="w-9 h-9 rounded-xl bg-primary/10 border border-primary/20 flex items-center justify-center">
          <ShieldCheck className="w-4 h-4 text-primary" />
        </div>
        <div>
          <h2 className="text-xl font-medium tracking-tight">Screening checklist</h2>
          <p className="text-[13px] text-foreground-muted">Model-guided checks to complete before merging.</p>
        </div>
      </div>
      <div className="grid gap-3 md:grid-cols-3">
        {suggestions.map((suggestion, index) => (
          <div key={index} className="glass-card rounded-2xl border border-border p-5">
            <div className="flex items-center gap-2 mb-3">
              <span className={`px-2 py-1 rounded-md text-[10px] font-bold uppercase tracking-wider ${
                suggestion.priority === 'High' ? 'bg-danger/10 text-danger' : suggestion.priority === 'Medium' ? 'bg-warning/10 text-warning' : 'bg-success/10 text-success'
              }`}>{suggestion.priority}</span>
              <h3 className="text-[13px] font-medium">{suggestion.title}</h3>
            </div>
            <p className="text-[13px] leading-relaxed text-foreground-muted">{suggestion.action}</p>
          </div>
        ))}
      </div>
    </section>
  );
}
