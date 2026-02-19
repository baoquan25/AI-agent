export const API_BASE = process.env.NEXT_PUBLIC_API_BASE ?? 'http://localhost:8000';
export const AI_AGENT_URL = `${API_BASE}/agent/chat`;


export function getTerminalWsUrl(): string {
  const base = API_BASE.replace(/^http/, 'ws');
  const uid = typeof window !== 'undefined' ? getUserId() : 'default_user';
  return `${base}/terminal/pty?user_id=${encodeURIComponent(uid)}`;
}

export function getUserId(): string {
  if (typeof window === 'undefined') return 'default_user';
  let uid = localStorage.getItem('X_USER_ID');
  if (!uid) {
    uid = 'user_' + Date.now();
    localStorage.setItem('X_USER_ID', uid);
  }
  return uid;
}

export function apiHeaders(): Record<string, string> {
  return {
    'X-User-ID': getUserId(),
    'Content-Type': 'application/json',
  };
}

export function escapeHtml(s: string): string {
  return String(s)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

export function escapeHtmlAttr(s: string): string {
  return String(s)
    .replace(/&/g, '&amp;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;');
}

export function stripAnsi(s: string | undefined): string {
  if (!s) return '';
  return String(s)
    .replace(/\x1b\[[0-9;]*[a-zA-Z]/g, '')
    .replace(/\[[0-9]{1,3}m/g, '');
}

export function formatFileSize(bytes: number): string {
  if (bytes < 1024) return bytes + ' B';
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB';
  return (bytes / (1024 * 1024)).toFixed(1) + ' MB';
}
