'use client';

import { useEffect, useRef } from 'react';
import { Terminal } from '@xterm/xterm';
import { FitAddon } from '@xterm/addon-fit';
import '@xterm/xterm/css/xterm.css';
import { getTerminalWsUrl } from '../../lib/utils';

type TerminalPanelProps = {
  active: boolean;
  error: string | null;
  containerRef: React.RefObject<HTMLDivElement | null>;
  onError: (msg: string | null) => void;
};

export function TerminalPanel({ active, error, containerRef, onError }: TerminalPanelProps) {
  const instanceRef = useRef<{ term: Terminal; fit: FitAddon; ws: WebSocket } | null>(null);

  useEffect(() => {
    if (!active || !containerRef.current) return;
    if (instanceRef.current) return;

    const container = containerRef.current;
    const term = new Terminal({
      cursorBlink: true,
      theme: { background: '#000000', foreground: '#ccc' },
      fontSize: 13,
      fontFamily: 'Menlo, Monaco, "Courier New", monospace',
    });
    const fit = new FitAddon();
    term.loadAddon(fit);
    term.open(container);
    fit.fit();

    const wsUrl = getTerminalWsUrl();
    const ws = new WebSocket(wsUrl);
    ws.binaryType = 'arraybuffer';

    ws.onopen = () => {
      onError(null);
      requestAnimationFrame(() => {
        fit.fit();
        if (ws.readyState === WebSocket.OPEN) {
          ws.send(JSON.stringify({ type: 'resize', cols: term.cols, rows: term.rows }));
        }
      });
    };
    ws.onmessage = (ev: MessageEvent) => {
      if (ev.data instanceof ArrayBuffer) term.write(new TextDecoder().decode(ev.data));
      else if (typeof ev.data === 'string') term.write(ev.data);
    };
    ws.onerror = () => onError('WebSocket error');
    ws.onclose = () => onError('Terminal disconnected');

    term.onData((data) => {
      if (ws.readyState === WebSocket.OPEN) ws.send(new TextEncoder().encode(data));
    });

    const resizeObserver = new ResizeObserver(() => {
      fit.fit();
      if (ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify({ type: 'resize', cols: term.cols, rows: term.rows }));
      }
    });
    resizeObserver.observe(container);

    instanceRef.current = { term, fit, ws };

    return () => {
      resizeObserver.disconnect();
      ws.close();
      term.dispose();
      instanceRef.current = null;
    };
  }, [active, containerRef, onError]);

  if (!active) return null;

  return (
    <div className="panel-scroll terminal-panel">
      {error && <div className="terminal-status" style={{ padding: 8, color: 'var(--error)', fontSize: 12 }}>{error}</div>}
      <div ref={containerRef as React.RefObject<HTMLDivElement>} className="xterm-container" style={{ width: '100%', height: '100%', minHeight: 120 }} />
    </div>
  );
}
