export interface AppSettings {
  llmApiKey: string;
  llmEndpoint: string;
  llmModel: string;
}

const STORAGE_KEY = 'devshield_settings';

const defaults: AppSettings = {
  llmApiKey: '',
  llmEndpoint: 'https://generativelanguage.googleapis.com/v1beta/openai/',
  llmModel: 'gemini-2.0-flash',
};

export function getSettings(): AppSettings {
  if (typeof window === 'undefined') return defaults;
  try {
    const stored = localStorage.getItem(STORAGE_KEY);
    if (!stored) return defaults;
    return { ...defaults, ...JSON.parse(stored) };
  } catch {
    return defaults;
  }
}

export function saveSettings(settings: AppSettings): void {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(settings));
}

export function hasApiKey(settings?: AppSettings): boolean {
  const s = settings ?? getSettings();
  return Boolean(s.llmApiKey.trim());
}
