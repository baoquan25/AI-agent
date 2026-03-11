'use client';

import { useState, useCallback, useRef } from 'react';
import * as fsApi from '../lib/api/fs';
import type { FileEdit } from '../lib/types';

export function useDiffReview(
  setFileContentDirect: (path: string, content: string | null) => void,
  currentFilePath: string | null,
) {
  const [pendingDiffs, setPendingDiffs] = useState<FileEdit[]>([]);
  const [reviewIndex, setReviewIndex] = useState(0);

  const currentFilePathRef = useRef(currentFilePath);
  currentFilePathRef.current = currentFilePath;

  const pendingDiffsRef = useRef(pendingDiffs);
  pendingDiffsRef.current = pendingDiffs;

  const addDiffs = useCallback((edits: FileEdit[]) => {
    if (!edits || edits.length === 0) return;
    setPendingDiffs(edits);
    setReviewIndex(0);
  }, []);

  const removeDiff = useCallback((path: string) => {
    setPendingDiffs((prev) => {
      const next = prev.filter((d) => d.path !== path);
      return next;
    });
    setReviewIndex((idx) => Math.min(idx, Math.max(0, pendingDiffsRef.current.length - 2)));
  }, []);

  const acceptDiff = useCallback((path: string) => {
    const diff = pendingDiffsRef.current.find((d) => d.path === path);
    if (!diff) return;

    setFileContentDirect(path, diff.new_content);
    removeDiff(path);
  }, [setFileContentDirect, removeDiff]);

  const rejectDiff = useCallback(async (path: string) => {
    const diff = pendingDiffsRef.current.find((d) => d.path === path);
    if (!diff) return;

    if (diff.action === 'create') {
      await fsApi.deletePath(path).catch(() => {});
      setFileContentDirect(path, null);
    } else if (diff.action === 'delete' && diff.old_content != null) {
      await fsApi.createFile(path, diff.old_content).catch(() => {});
      setFileContentDirect(path, diff.old_content);
    } else if (diff.old_content != null) {
      await fsApi.putFileContent(path, diff.old_content).catch(() => {});
      setFileContentDirect(path, diff.old_content);
    }

    removeDiff(path);
  }, [setFileContentDirect, removeDiff]);

  const acceptAll = useCallback(() => {
    for (const diff of pendingDiffsRef.current) {
      setFileContentDirect(diff.path, diff.new_content);
    }
    setPendingDiffs([]);
    setReviewIndex(0);
  }, [setFileContentDirect]);

  const rejectAll = useCallback(async () => {
    for (const diff of pendingDiffsRef.current) {
      if (diff.action === 'create') {
        await fsApi.deletePath(diff.path).catch(() => {});
        setFileContentDirect(diff.path, null);
      } else if (diff.action === 'delete' && diff.old_content != null) {
        await fsApi.createFile(diff.path, diff.old_content).catch(() => {});
        setFileContentDirect(diff.path, diff.old_content);
      } else if (diff.old_content != null) {
        await fsApi.putFileContent(diff.path, diff.old_content).catch(() => {});
        setFileContentDirect(diff.path, diff.old_content);
      }
    }
    setPendingDiffs([]);
    setReviewIndex(0);
  }, [setFileContentDirect]);

  const currentDiff = pendingDiffs[reviewIndex] ?? null;
  const hasDiffs = pendingDiffs.length > 0;
  const diffForFile = useCallback(
    (path: string) => pendingDiffs.find((d) => d.path === path) ?? null,
    [pendingDiffs],
  );

  return {
    pendingDiffs,
    reviewIndex,
    setReviewIndex,
    currentDiff,
    hasDiffs,
    diffForFile,
    addDiffs,
    acceptDiff,
    rejectDiff,
    acceptAll,
    rejectAll,
  };
}
