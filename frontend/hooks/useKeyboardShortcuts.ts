'use client';

import React, { useEffect } from 'react';

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
  const {
    saveAllFiles,
    openSearchTab,
    closeTab,
    currentFilePath,
    treeCreateMode,
    cancelCreate,
    setContextMenu,
    setRenameNode,
    fileCache,
    chatLoading,
  } = options;

  useEffect(() => {
    const onKeyDown = (e: KeyboardEvent) => {
      if (e.ctrlKey && e.key === 's') {
        e.preventDefault();
        if (!chatLoading) saveAllFiles();
      }
      if (e.ctrlKey && e.key === 'p') {
        e.preventDefault();
        if (!chatLoading) openSearchTab();
      }
      if (e.ctrlKey && e.key === 'w' && currentFilePath) {
        e.preventDefault();
        closeTab(currentFilePath);
      }
      if (e.key === 'Escape') {
        if (treeCreateMode) cancelCreate();
        setContextMenu((prev: { show: boolean }) => ({ ...prev, show: false }));
        setRenameNode(null);
      }
    };
    window.addEventListener('keydown', onKeyDown);
    return () => window.removeEventListener('keydown', onKeyDown);
  }, [saveAllFiles, openSearchTab, closeTab, currentFilePath, treeCreateMode, cancelCreate, setContextMenu, setRenameNode, chatLoading]);

  useEffect(() => {
    const onBeforeUnload = (e: BeforeUnloadEvent) => {
      if (Object.values(fileCache).some((v) => v.modified)) e.preventDefault();
    };
    window.addEventListener('beforeunload', onBeforeUnload);
    return () => window.removeEventListener('beforeunload', onBeforeUnload);
  }, [fileCache]);
}
