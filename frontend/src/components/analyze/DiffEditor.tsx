'use client';

import React, { useRef } from 'react';
import { FileCode2, Upload } from 'lucide-react';
import { loadUpload } from '@/lib/upload';

export const starterDiff = `diff --git a/src/api/auth.ts b/src/api/auth.ts
index e9f6d1a..0c5bb21 100644
--- a/src/api/auth.ts
+++ b/src/api/auth.ts
@@ -24,7 +24,8 @@ export async function login(req: Request) {
   const { email, password } = await req.json();
-  const user = await db.users.findFirst({ where: { email } });
+  const query = "SELECT * FROM users WHERE email = '" + email + "'";
+  const user = await db.raw(query);
   return createSession(user);
 }`;

interface DiffEditorProps {
  diff: string;
  onChange: (value: string) => void;
  onToast: (message: string) => void;
  onError: (message: string) => void;
}

export default function DiffEditor({ diff, onChange, onToast, onError }: DiffEditorProps) {
  const fileRef = useRef<HTMLInputElement>(null);

  const loadFile = async (file: File | undefined | null) => {
    if (!file) return;
    const result = await loadUpload(file, 'diff');
    if ('error' in result) {
      onError(result.error);
      return;
    }
    onChange(result.content);
    onToast(`${file.name} ready to review`);
  };

  return (
    <div className="flex-1 flex flex-col border-b lg:border-b-0 lg:border-r border-border min-h-[400px]">
      <div className="bg-surface border-b border-border px-4 py-3 flex items-center justify-between">
        <div className="flex items-center gap-4">
          <button className="text-[12px] font-medium text-foreground border-b border-foreground pb-1">Editor</button>
        </div>
        <button onClick={() => fileRef.current?.click()} className="text-[12px] text-foreground-muted hover:text-foreground flex items-center gap-1.5 transition-colors">
          <Upload className="w-3.5 h-3.5" /> Upload .diff
        </button>
      </div>

      <div className="flex-1 min-h-[340px] flex relative bg-[#0D0D0F]">
        <div className="w-12 bg-surface flex flex-col items-center py-4 text-[11px] font-mono text-foreground-muted/40 border-r border-border select-none">
          {Array.from({ length: 20 }, (_, i) => <span key={i} className="leading-6">{i + 1}</span>)}
        </div>
        <textarea
          value={diff}
          onChange={e => onChange(e.target.value)}
          placeholder={starterDiff}
          spellCheck={false}
          className="min-w-0 flex-1 bg-transparent p-4 text-[13px] font-mono text-foreground/80 focus:outline-none resize-none leading-6 placeholder:text-foreground-muted/30"
        />

        {!diff && (
          <div
            onDragOver={e => e.preventDefault()}
            onDrop={e => {
              e.preventDefault();
              loadFile(e.dataTransfer.files?.[0]);
            }}
            className="absolute inset-0 m-4 sm:m-8 border-2 border-dashed border-border rounded-xl flex flex-col items-center justify-center bg-surface/50 backdrop-blur-sm"
          >
            <FileCode2 className="w-8 h-8 text-foreground-muted mb-3" />
            <span className="text-[14px] font-medium">Paste diff or drag file</span>
          </div>
        )}
      </div>

      <input
        ref={fileRef}
        className="hidden"
        type="file"
        accept=".diff,.patch,.txt"
        onChange={e => {
          loadFile(e.target.files?.[0]);
          e.target.value = '';
        }}
      />
    </div>
  );
}
