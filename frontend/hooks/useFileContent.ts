'use client';

import { useState, useEffect, useCallback, useRef } from 'react';
import * as fsApi from '../lib/api/fs';

type SetOutputHtml = (html: string) => void;

export function useFileContent(
  currentFilePath: string | null,
  fileCache: Record<string, { content: string; modified: boolean }>,
  setFileCache: React.Dispatch<React.SetStateAction<Record<string, { content: string; modified: boolean }>>>,
  setOutputHtml: SetOutputHtml
) {
  const [codeValue, setCodeValue] = useState('');
  const [hasUnsavedChanges, setHasUnsavedChanges] = useState(false);

  const fileCacheRef = useRef(fileCache);
  fileCacheRef.current = fileCache;

  const currentFilePathRef = useRef(currentFilePath);
  currentFilePathRef.current = currentFilePath;

  const inFlightRef = useRef<Map<string, Promise<void>>>(new Map());

  // Track paths saved in the last few seconds so the WebSocket "updated" handler
  // can skip re-reading files the user just saved locally.
  const recentlySavedRef = useRef<Set<string>>(new Set());

  const loadFileContent = useCallback(
    async (path: string) => {
      const cached = fileCacheRef.current[path];
      if (cached) {
        setCodeValue(cached.content);
        setHasUnsavedChanges(cached.modified);
        setOutputHtml(`<span class="output-success">${path} (from cache)</span>`);
        return;
      }

      const existing = inFlightRef.current.get(path);
      if (existing) {
        await existing;
        const nowCached = fileCacheRef.current[path];
        if (nowCached) {
          setCodeValue(nowCached.content);
          setHasUnsavedChanges(nowCached.modified);
        }
        return;
      }

      const promise = (async () => {
        try {
          const data = await fsApi.getFileContent(path);
          if (data.success && data.content != null) {
            setCodeValue(data.content);
            setHasUnsavedChanges(false);
            setFileCache((prev) => ({ ...prev, [path]: { content: data.content!, modified: false } }));
            setOutputHtml(`<span class="output-success">Loaded: ${path}</span>`);
          } else {
            setOutputHtml(`<span class="output-error">Failed: ${path}</span>`);
          }
        } catch (e) {
          setOutputHtml(`<span class="output-error">${(e as Error).message}</span>`);
        } finally {
          inFlightRef.current.delete(path);
        }
      })();

      inFlightRef.current.set(path, promise);
      await promise;
    },
    [setFileCache, setOutputHtml]
  );

  useEffect(() => {
    if (currentFilePath) {
      loadFileContent(currentFilePath);
    } else {
      setCodeValue('');
      setHasUnsavedChanges(false);
    }
    // loadFileContent is now stable (deps: setFileCache, setOutputHtml — both from useState)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [currentFilePath]);

  const handleCodeChange = useCallback(
    (value: string) => {
      setCodeValue(value);
      if (currentFilePath) {
        setFileCache((prev) => ({ ...prev, [currentFilePath]: { content: value, modified: true } }));
        setHasUnsavedChanges(true);
      }
    },
    [currentFilePath, setFileCache]
  );

  const saveAllFiles = useCallback(async () => {
    const cache = fileCacheRef.current;
    const modifiedPaths = Object.entries(cache).filter(([, v]) => v.modified).map(([k]) => k);
    if (modifiedPaths.length === 0) {
      setOutputHtml('<span class="output-success">No unsaved changes</span>');
      return;
    }
    setOutputHtml('<span style="color:var(--muted)">Saving...</span>');
    let savedCount = 0;
    const failed: string[] = [];
    for (const path of modifiedPaths) {
      try {
        const data = await fsApi.putFileContent(path, cache[path].content);
        if (data.success) {
          setFileCache((prev) => ({ ...prev, [path]: { ...prev[path], modified: false } }));
          recentlySavedRef.current.add(path);
          setTimeout(() => recentlySavedRef.current.delete(path), 3000);
          savedCount++;
        } else failed.push(path);
      } catch {
        failed.push(path);
      }
    }
    if (failed.length === 0) {
      setOutputHtml(`<span class="output-success">Saved ${savedCount} file(s)</span>`);
      setHasUnsavedChanges(false);
    } else {
      setOutputHtml(`<span class="output-error">Saved ${savedCount}/${modifiedPaths.length}. Failed: ${failed.join(', ')}</span>`);
    }
  }, [setFileCache, setOutputHtml]);

  const wasRecentlySaved = useCallback((path: string) => recentlySavedRef.current.has(path), []);

  const setFileContentDirect = useCallback(
    (path: string, content: string | null) => {
      if (content != null) {
        setFileCache((prev) => ({ ...prev, [path]: { content, modified: false } }));
        if (path === currentFilePathRef.current) {
          setCodeValue(content);
          setHasUnsavedChanges(false);
        }
      } else {
        setFileCache((prev) => {
          const next = { ...prev };
          delete next[path];
          return next;
        });
        if (path === currentFilePathRef.current) {
          setCodeValue('');
          setHasUnsavedChanges(false);
        }
      }
    },
    [setFileCache],
  );

  return { codeValue, setCodeValue, hasUnsavedChanges, loadFileContent, handleCodeChange, saveAllFiles, wasRecentlySaved, setFileContentDirect };
}
