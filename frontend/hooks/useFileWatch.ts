'use client';

import { useEffect, useRef, useCallback } from 'react';
import { API_BASE } from '../lib/constants';
import { getUserId } from '../lib/utils';

export type FileChangeEvent = {
  changeType: 'created' | 'updated' | 'deleted' | 'renamed';
  path: string;
  isDirectory: boolean;
  oldPath?: string;
};

type FileChangeMessage = {
  type: 'fileChange';
  changes: FileChangeEvent[];
};

type WsMessage = FileChangeMessage | { type: 'ping' } | { type: 'ready'; userId: string; watchPath: string };

export type FileChangeHandler = (changes: FileChangeEvent[]) => void;

const RECONNECT_BASE_MS = 1000;
const RECONNECT_MAX_MS = 30000;

export function useFileWatch(onFileChange: FileChangeHandler) {
  const handlerRef = useRef(onFileChange);
  handlerRef.current = onFileChange;

  const wsRef = useRef<WebSocket | null>(null);
  const reconnectAttemptRef = useRef(0);
  const reconnectTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const mountedRef = useRef(true);

  const connect = useCallback(() => {
    if (!mountedRef.current) return;
    if (wsRef.current && wsRef.current.readyState <= WebSocket.OPEN) return;

    const baseWs = API_BASE.replace(/^http/, 'ws');
    const url = `${baseWs}/fs/watch?user_id=${encodeURIComponent(getUserId())}`;
    const ws = new WebSocket(url);
    wsRef.current = ws;

    ws.onopen = () => {
      reconnectAttemptRef.current = 0;
    };

    ws.onmessage = (ev: MessageEvent) => {
      if (typeof ev.data !== 'string') return;
      try {
        const msg: WsMessage = JSON.parse(ev.data);
        if (msg.type === 'fileChange') {
          handlerRef.current(msg.changes);
        } else if (msg.type === 'ping') {
          try { ws.send('{"type":"pong"}'); } catch { /* ignore */ }
        }
      } catch { /* malformed JSON — skip */ }
    };

    ws.onclose = () => {
      wsRef.current = null;
      scheduleReconnect();
    };

    ws.onerror = () => {
      // onclose will fire after onerror
    };
  }, []);

  const scheduleReconnect = useCallback(() => {
    if (!mountedRef.current) return;
    if (reconnectTimerRef.current) return;

    const attempt = reconnectAttemptRef.current;
    const delay = Math.min(RECONNECT_BASE_MS * Math.pow(2, attempt), RECONNECT_MAX_MS);
    reconnectAttemptRef.current = attempt + 1;

    reconnectTimerRef.current = setTimeout(() => {
      reconnectTimerRef.current = null;
      connect();
    }, delay);
  }, [connect]);

  useEffect(() => {
    mountedRef.current = true;
    connect();

    return () => {
      mountedRef.current = false;
      if (reconnectTimerRef.current) {
        clearTimeout(reconnectTimerRef.current);
        reconnectTimerRef.current = null;
      }
      if (wsRef.current) {
        wsRef.current.onclose = null;
        wsRef.current.close();
        wsRef.current = null;
      }
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return wsRef;
}
