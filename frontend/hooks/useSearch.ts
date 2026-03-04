'use client';

import { useState, useEffect, useCallback, useRef } from 'react';
import { searchFiles as searchFilesApi } from '../lib/api/fs';

export function useSearch() {
  const [leftBarTab, setLeftBarTab] = useState<'files' | 'search'>('files');
  const [searchPattern, setSearchPattern] = useState('');
  const [searchResults, setSearchResults] = useState<string[]>([]);
  const searchInputRef = useRef<HTMLInputElement>(null);

  const searchPatternRef = useRef(searchPattern);
  searchPatternRef.current = searchPattern;

  const searchFiles = useCallback(async (patternOverride?: string) => {
    const pattern = (patternOverride ?? searchPatternRef.current).trim();
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
  }, []);

  const openSearchTab = useCallback(() => {
    setLeftBarTab('search');
    setSearchResults([]);
    setTimeout(() => searchInputRef.current?.focus(), 50);
  }, []);

  useEffect(() => {
    if (leftBarTab !== 'search') return;
    if (!searchPattern.trim()) {
      setSearchResults([]);
      return;
    }
    const t = setTimeout(() => searchFiles(), 300);
    return () => clearTimeout(t);
  }, [leftBarTab, searchPattern, searchFiles]);

  return {
    leftBarTab,
    setLeftBarTab,
    searchPattern,
    setSearchPattern,
    searchResults,
    searchFiles,
    openSearchTab,
    searchInputRef,
  };
}
