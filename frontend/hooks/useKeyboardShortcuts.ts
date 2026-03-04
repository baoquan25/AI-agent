'use client';

import React, { useEffect, useRef } from 'react';

type FileCache = Record<string, { content: string; modified: boolean }>;

export function useKeyboardShortcuts(options: {
  saveAllFiles: () => void;
  openSearchTab: () => void;
  closeTab: (path: string) => void;
  currentFilePath: string | null;
  treeCreateMode: 'file' | 'folder' | null;
  cancelCreate: () => void;
  setContextMenu: (arg: unknown) => void;
  setRenameNode: (arg: unknown) => void;
  fileCache: FileCache;
  chatLoading: boolean;
}) {
  const optionsRef = useRef(options);
  optionsRef.current = options;

  useEffect(() => {
    const onKeyDown = (e: KeyboardEvent) => {
      const o = optionsRef.current;
      if (e.ctrlKey && e.key === 's') {
        e.preventDefault();
        if (!o.chatLoading) o.saveAllFiles();
      }
      if (e.ctrlKey && e.key === 'p') {
        e.preventDefault();
        if (!o.chatLoading) o.openSearchTab();
      }
      if (e.ctrlKey && e.key === 'w' && o.currentFilePath) {
        e.preventDefault();
        o.closeTab(o.currentFilePath);
      }
      if (e.key === 'Escape') {
        if (o.treeCreateMode) o.cancelCreate();
        o.setContextMenu((prev: { show: boolean }) => ({ ...prev, show: false }));
        o.setRenameNode(null);
      }
    };
    window.addEventListener('keydown', onKeyDown);
    return () => window.removeEventListener('keydown', onKeyDown);
  }, []);

  useEffect(() => {
    const onBeforeUnload = (e: BeforeUnloadEvent) => {
      if (Object.values(optionsRef.current.fileCache).some((v) => v.modified)) e.preventDefault();
    };
    window.addEventListener('beforeunload', onBeforeUnload);
    return () => window.removeEventListener('beforeunload', onBeforeUnload);
  }, []);
}
