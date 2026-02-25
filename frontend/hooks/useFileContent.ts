'use client';

import { useState, useEffect, useCallback } from 'react';
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

  const loadFileContent = useCallback(
    async (path: string) => {
      const cached = fileCache[path];
      if (cached) {
        setCodeValue(cached.content);
        setHasUnsavedChanges(cached.modified);
        setOutputHtml(`<span class="output-success">${path} (from cache)</span>`);
        return;
      }
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
      }
    },
    [fileCache, setFileCache, setOutputHtml]
  );

  useEffect(() => {
    if (currentFilePath) {
      loadFileContent(currentFilePath);
    } else {
      setCodeValue('');
      setHasUnsavedChanges(false);
    }
  }, [currentFilePath, loadFileContent]);

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
    const modifiedPaths = Object.entries(fileCache).filter(([, v]) => v.modified).map(([k]) => k);
    if (modifiedPaths.length === 0) {
      setOutputHtml('<span class="output-success">No unsaved changes</span>');
      return;
    }
    setOutputHtml('<span style="color:var(--muted)">Saving...</span>');
    let savedCount = 0;
    const failed: string[] = [];
    for (const path of modifiedPaths) {
      try {
        const data = await fsApi.putFileContent(path, fileCache[path].content);
        if (data.success) {
          setFileCache((prev) => ({ ...prev, [path]: { ...prev[path], modified: false } }));
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
  }, [fileCache, setFileCache, setOutputHtml]);

  return { codeValue, setCodeValue, hasUnsavedChanges, loadFileContent, handleCodeChange, saveAllFiles };
}
