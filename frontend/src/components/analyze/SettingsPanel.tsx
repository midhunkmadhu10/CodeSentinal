'use client';

import React from 'react';
import { Info } from 'lucide-react';
import type { SettingsStatus } from '@/lib/api';

interface SettingsPanelProps {
  status: SettingsStatus | null;
}

export default function SettingsPanel({ status }: SettingsPanelProps) {
  return (
    <div className="max-w-2xl mx-auto animate-fade-in">
      <div className="mb-10">
        <h2 className="text-3xl font-medium tracking-tight mb-3">Configuration</h2>
        <p className="text-foreground-muted font-light">
          The LLM provider is configured on the backend via environment variables.
          API keys are never stored in the browser or sent from this page.
        </p>
      </div>

      <div className="glass-card rounded-2xl p-5 sm:p-8 space-y-6">
        <div className="space-y-5">
          <div className="flex items-center justify-between gap-4">
            <div>
              <div className="text-[13px] font-medium">LLM provider</div>
              <div className="text-[12px] text-foreground-muted">
                {status === null
                  ? 'Checking backend status…'
                  : status.llm_configured
                    ? 'Configured and ready'
                    : 'Not configured — set LLM_ENDPOINT, LLM_MODEL, and LLM_API_KEY in the backend environment'}
              </div>
            </div>
            <span
              className={`px-3 py-1 rounded-full text-[11px] font-bold uppercase tracking-wider ${
                status?.llm_configured
                  ? 'bg-success/10 text-success border border-success/20'
                  : 'bg-warning/10 text-warning border border-warning/20'
              }`}
            >
              {status?.llm_configured ? 'Ready' : 'Missing'}
            </span>
          </div>

          <div>
            <div className="text-[13px] font-medium text-foreground-muted mb-1">Model</div>
            <div className="bg-surface-card border border-border rounded-xl px-4 py-3 text-[14px] font-mono">
              {status?.llm_model || 'Default (set LLM_MODEL on the backend)'}
            </div>
          </div>

          <div>
            <div className="text-[13px] font-medium text-foreground-muted mb-1">Endpoint</div>
            <div className="bg-surface-card border border-border rounded-xl px-4 py-3 text-[14px] font-mono break-all">
              {status?.llm_endpoint || 'Default (set LLM_ENDPOINT on the backend)'}
            </div>
          </div>
        </div>

        <div className="pt-4 border-t border-border flex items-start gap-3 text-[12px] text-foreground-muted">
          <Info className="w-4 h-4 mt-0.5 shrink-0" />
          <p>
            To change the provider, edit the backend <code>.env</code> file and restart the
            backend. Requests are authenticated with your session token; the LLM API key
            stays server-side at all times.
          </p>
        </div>
      </div>
    </div>
  );
}
