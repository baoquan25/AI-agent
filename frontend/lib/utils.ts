import { API_BASE } from "./constants";

/** User mặc định dùng cho mọi request (X-User-ID, terminal). */
const DEFAULT_USER_ID = "user-001";

export function getUserId(): string {
  return DEFAULT_USER_ID;
}

/** Header cho API request (có kèm user ID). */
export function apiHeaders(): Record<string, string> {
  return {
    "X-User-ID": getUserId(),
    "Content-Type": "application/json",
  };
}

/** URL WebSocket cho terminal (PTY), có gắn user_id. */
export function getTerminalWsUrl(): string {
  const baseWs = API_BASE.replace(/^http/, "ws");
  return `${baseWs}/terminal/pty?user_id=${encodeURIComponent(getUserId())}`;
}

const escapeByMap = (s: string, map: Record<string, string>): string =>
  String(s).replace(/[&<>"']/g, (ch) => map[ch] ?? ch);

export const escapeHtml = (s: string) =>
  escapeByMap(s, {
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    '"': "&quot;",
  });

/** Bỏ mã ANSI (màu/format) trong chuỗi terminal. */
export function stripAnsi(s = ""): string {
  return String(s)
    .replace(/\x1b\[[0-9;]*[a-zA-Z]/g, "")
    .replace(/\[[0-9]{1,3}m/g, "");
}

/** Format số byte thành dạng đọc được (B, KB, MB). */
export function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}