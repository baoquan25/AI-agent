'use client';

import { useState, useCallback } from 'react';
import type { TabItem, FileCacheItem } from '../lib/types';

export function useFileTabs() {
  const [openTabs, setOpenTabs] = useState<TabItem[]>([]);
  const [currentFilePath, setCurrentFilePath] = useState<string | null>(null);
  const [fileCache, setFileCache] = useState<Record<string, FileCacheItem>>({});

  const addTab = useCallback((path: string, name: string) => {
    setOpenTabs((prev) => (prev.some((t) => t.path === path) ? prev : [...prev, { path, name }]));
    setCurrentFilePath(path);
  }, []);

  const switchTab = useCallback((path: string) => {
    setCurrentFilePath(path);
  }, []);

  const closeTab = useCallback((path: string) => {
    setOpenTabs((prev) => {
      const cached = prev.find((t) => t.path === path);
      const next = prev.filter((t) => t.path !== path);
      setCurrentFilePath((cur) => (cur === path ? (next.length ? next[next.length - 1].path : null) : cur));
      return next;
    });
  }, []);

  return {
    openTabs,
    setOpenTabs,
    currentFilePath,
    setCurrentFilePath,
    fileCache,
    setFileCache,
    addTab,
    switchTab,
    closeTab,
  };
}
