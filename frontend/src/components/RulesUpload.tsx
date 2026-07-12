'use client';

import React, { useRef } from 'react';
import { FileText, Upload, X, File } from 'lucide-react';

interface RulesUploadProps {
  rules: string;
  onRulesChange: (rules: string) => void;
  disabled?: boolean;
}

export default function RulesUpload({ rules, onRulesChange, disabled }: RulesUploadProps) {
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [fileName, setFileName] = React.useState<string | null>(null);

  const handleFileUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    setFileName(file.name);
    const reader = new FileReader();
    reader.onload = (event) => {
      const text = event.target?.result as string;
      onRulesChange(text);
    };
    reader.readAsText(file);
  };

  const handleClear = () => {
    onRulesChange('');
    setFileName(null);
    if (fileInputRef.current) {
      fileInputRef.current.value = '';
    }
  };

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <label className="text-sm font-medium text-foreground">Security Rules</label>
        <span className="text-xs text-foreground-muted">Upload SECURITY.md, coding rules, or API docs</span>
      </div>

      <input
        ref={fileInputRef}
        type="file"
        accept=".md,.txt,.rst"
        onChange={handleFileUpload}
        className="hidden"
        disabled={disabled}
      />

      {rules ? (
        <div className="bg-surface border border-border rounded-lg p-4">
          <div className="flex items-start justify-between">
            <div className="flex items-center gap-2">
              <FileText className="w-4 h-4 text-primary" />
              <div>
                <p className="text-sm font-medium text-foreground">{fileName || 'rules.md'}</p>
                <p className="text-xs text-foreground-muted">{rules.length.toLocaleString()} characters</p>
              </div>
            </div>
            <button
              type="button"
              onClick={handleClear}
              className="p-1 text-foreground-muted hover:text-danger transition-colors"
              disabled={disabled}
            >
              <X className="w-4 h-4" />
            </button>
          </div>
          <div className="mt-3 max-h-32 overflow-y-auto rounded bg-background/50 p-2">
            <pre className="text-xs text-foreground-muted leading-relaxed whitespace-pre-wrap font-mono">
              {rules.slice(0, 500)}
              {rules.length > 500 ? '...' : ''}
            </pre>
          </div>
        </div>
      ) : (
        <div
          onClick={() => fileInputRef.current?.click()}
          className="flex flex-col items-center justify-center h-32 border-2 border-dashed border-border rounded-lg bg-surface/50 cursor-pointer hover:border-primary/50 hover:bg-surface transition-all"
        >
          <File className="w-6 h-6 text-foreground-muted mx-auto mb-2" />
          <p className="text-sm text-foreground-muted">Click to upload rules</p>
          <p className="text-xs text-foreground-muted/50 mt-1">Supports .md, .txt, .rst</p>
        </div>
      )}
    </div>
  );
}