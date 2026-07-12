'use client';

import React, { useRef } from 'react';
import { FileText, Upload, Clipboard } from 'lucide-react';

interface DiffInputProps {
  diff: string;
  onChange: (diff: string) => void;
  disabled?: boolean;
}

export default function DiffInput({ diff, onChange, disabled }: DiffInputProps) {
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [activeTab, setActiveTab] = React.useState<'paste' | 'upload'>('paste');

  const handleFileUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    const reader = new FileReader();
    reader.onload = (event) => {
      const text = event.target?.result as string;
      onChange(text);
    };
    reader.readAsText(file);
  };

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <label className="text-sm font-medium text-foreground">Code Diff</label>
        <span className="text-xs text-foreground-muted">Paste or upload a .diff file</span>
      </div>

      {/* Tabs */}
      <div className="flex border border-border rounded-lg overflow-hidden">
        <button
          type="button"
          onClick={() => setActiveTab('paste')}
          className={`flex-1 flex items-center justify-center gap-1.5 px-3 py-2 text-xs font-medium transition-colors ${
            activeTab === 'paste'
              ? 'bg-primary/10 text-primary border-b-2 border-primary'
              : 'bg-surface text-foreground-muted hover:text-foreground'
          }`}
        >
          <Clipboard className="w-3.5 h-3.5" />
          Paste Diff
        </button>
        <button
          type="button"
          onClick={() => {
            setActiveTab('upload');
            fileInputRef.current?.click();
          }}
          className={`flex-1 flex items-center justify-center gap-1.5 px-3 py-2 text-xs font-medium transition-colors ${
            activeTab === 'upload'
              ? 'bg-primary/10 text-primary border-b-2 border-primary'
              : 'bg-surface text-foreground-muted hover:text-foreground'
          }`}
        >
          <Upload className="w-3.5 h-3.5" />
          Upload .diff
        </button>
      </div>

      {/* Textarea for paste */}
      {activeTab === 'paste' && (
        <textarea
          value={diff}
          onChange={(e) => onChange(e.target.value)}
          placeholder={`Paste your PR diff here...\n\ne.g.\ndiff --git a/src/auth.ts b/src/auth.ts\nindex a1b2c3d..e4f5g6h 100644\n--- a/src/auth.ts\n+++ b/src/auth.ts\n@@ -10,7 +10,7 @@`}
          disabled={disabled}
          className="w-full h-48 px-3 py-2.5 bg-surface border border-border rounded-lg text-foreground text-sm font-mono placeholder:text-foreground-muted/30 focus:outline-none focus:ring-2 focus:ring-primary/40 focus:border-primary transition-all resize-y disabled:opacity-50"
        />
      )}

      {/* Hidden file input */}
      <input
        ref={fileInputRef}
        type="file"
        accept=".diff,.patch,.txt"
        onChange={handleFileUpload}
        className="hidden"
        disabled={disabled}
      />

      {/* Upload status */}
      {activeTab === 'upload' && (
        <div
          onClick={() => fileInputRef.current?.click()}
          className="flex flex-col items-center justify-center h-48 border-2 border-dashed border-border rounded-lg bg-surface/50 cursor-pointer hover:border-primary/50 hover:bg-surface transition-all"
        >
          {diff ? (
            <div className="text-center p-4">
              <FileText className="w-8 h-8 text-primary mx-auto mb-2" />
              <p className="text-sm text-foreground">Diff loaded</p>
              <p className="text-xs text-foreground-muted mt-1">{diff.length.toLocaleString()} characters</p>
              <button
                type="button"
                onClick={(e) => {
                  e.stopPropagation();
                  onChange('');
                }}
                className="text-xs text-danger hover:underline mt-2"
              >
                Clear
              </button>
            </div>
          ) : (
            <div className="text-center p-4">
              <Upload className="w-8 h-8 text-foreground-muted mx-auto mb-2" />
              <p className="text-sm text-foreground-muted">Click to upload a .diff file</p>
              <p className="text-xs text-foreground-muted/50 mt-1">or drag and drop</p>
            </div>
          )}
        </div>
      )}
    </div>
  );
}