/** Only fields in a non-secret configuration template can enter a saved draft. */
export function readConfigDraft<T extends object>(key: string, defaults: T): T {
  try {
    const stored = JSON.parse(localStorage.getItem(key) ?? 'null');
    if (!stored || typeof stored !== 'object' || Array.isArray(stored)) return { ...defaults };
    const result = { ...defaults } as Record<string, unknown>;
    for (const [name, baseline] of Object.entries(defaults)) {
      const value = stored[name];
      if (typeof baseline === 'number' && typeof value === 'number' && Number.isFinite(value) && value >= 0) result[name] = value;
      else if (typeof baseline === 'boolean' && typeof value === 'boolean') result[name] = value;
      else if (baseline === null && (value === null || typeof value === 'number' && Number.isFinite(value) && value >= 0)) result[name] = value;
      else if (Array.isArray(baseline) && Array.isArray(value) && value.every(v => typeof v === 'string')) result[name] = value.slice(0, 200);
      else if (typeof baseline === 'string' && value === baseline) result[name] = value;
    }
    return result as T;
  } catch { return { ...defaults }; }
}
