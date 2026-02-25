'use client';

import { useState, useCallback, useRef } from 'react';

export function useTerminal() {
  const [outputTab, setOutputTab] = useState<'output' | 'terminal'>('output');
  const [terminalError, setTerminalError] = useState<string | null>(null);
  const terminalContainerRef = useRef<HTMLDivElement>(null);

  const openTerminalTab = useCallback(() => {
    setTerminalError(null);
    setOutputTab('terminal');
  }, []);

  return {
    outputTab,
    setOutputTab,
    terminalError,
    setTerminalError,
    terminalContainerRef,
    openTerminalTab,
  };
}
