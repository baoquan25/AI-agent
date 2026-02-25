'use client';

import { useState, useEffect, useCallback, useRef } from 'react';
import { searchFiles as searchFilesApi } from '../lib/api/fs';

export function useSearch() {
  const [sidebarTab, setSidebarTab] = useState<'files' | 'search'>('files');
  const [searchPattern, setSearchPattern] = useState('');
  const [searchResults, setSearchResults] = useState<string[]>([]);
  const searchInputRef = useRef<HTMLInputElement>(null);

  const searchFiles = useCallback(async (patternOverride?: string) => {
    const pattern = (patternOverride ?? searchPattern).trim();
    if (!pattern) {
      setSearchResults([]);
      return;
    }
    try {
      const data = await searchFilesApi(pattern, '');
      setSearchResults(data.success && data.matches?.length ? data.matches : []);
    } catch (e) {
      setSearchResults([`Error: ${(e as Error).message}`]);
    }
  }, [searchPattern]);

  const openSearchTab = useCallback(() => {
    setSidebarTab('search');
    setSearchResults([]);
    setTimeout(() => searchInputRef.current?.focus(), 50);
  }, []);

  useEffect(() => {
    if (sidebarTab !== 'search') return;
    if (!searchPattern.trim()) {
      setSearchResults([]);
      return;
    }
    const t = setTimeout(() => searchFiles(), 300);
    return () => clearTimeout(t);
  }, [sidebarTab, searchPattern, searchFiles]);

  return {
    sidebarTab,
    setSidebarTab,
    searchPattern,
    setSearchPattern,
    searchResults,
    searchFiles,
    openSearchTab,
    searchInputRef,
  };
}
