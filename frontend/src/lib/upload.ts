/** Client-side upload validation and safe file reading.
 *
 * These checks mirror the server-side limits in `backend/app/config.py`.
 * The server always re-validates; this is UX, not security.
 */

export const MAX_DIFF_FILE_BYTES = 500 * 1024; // ~500 KB, matches MAX_DIFF_BYTES
export const MAX_RULES_FILE_BYTES = 1024 * 1024; // ~1 MB, matches MAX_RULES_BYTES

const DIFF_EXTENSIONS = ['.diff', '.patch', '.txt'];
const RULES_EXTENSIONS = ['.md', '.txt'];

export type UploadKind = 'diff' | 'rules';

export function validateUpload(file: File, kind: UploadKind): string | null {
  const name = file.name.toLowerCase();
  const allowed = kind === 'diff' ? DIFF_EXTENSIONS : RULES_EXTENSIONS;
  if (!allowed.some(ext => name.endsWith(ext))) {
    return `Unsupported file type. Upload ${allowed.join(' / ')}.`;
  }
  const limit = kind === 'diff' ? MAX_DIFF_FILE_BYTES : MAX_RULES_FILE_BYTES;
  if (file.size > limit) {
    return `File is too large (${Math.ceil(file.size / 1024)} KB). The limit is ${limit / 1024} KB.`;
  }
  if (file.size === 0) {
    return `${file.name} is empty.`;
  }
  return null;
}

export function readTextFile(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(String(reader.result ?? ''));
    reader.onerror = () => reject(new Error(`Could not read ${file.name}.`));
    reader.readAsText(file);
  });
}

/** Validate and read an upload; returns an error message instead of throwing. */
export async function loadUpload(
  file: File,
  kind: UploadKind
): Promise<{ content: string } | { error: string }> {
  const validationError = validateUpload(file, kind);
  if (validationError) return { error: validationError };
  try {
    return { content: await readTextFile(file) };
  } catch (err) {
    return { error: err instanceof Error ? err.message : `Could not read ${file.name}.` };
  }
}
