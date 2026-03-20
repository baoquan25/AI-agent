'use client';

import { useState, useCallback, useRef } from 'react';
import * as fsApi from '../lib/api/fs';
import type { FileEdit } from '../lib/types';
import {
  areAllChangesResolved,
  buildLineDiff,
  buildResolvedContent,
  summarizeDecisions,
  type LineDecision,
} from '../lib/lineDiff';

export function useDiffReview(
  setFileContentDirect: (path: string, content: string | null) => void,
  _currentFilePath: string | null,
  addTab: (path: string, name: string) => void,
) {
  const [pendingDiffs, setPendingDiffs] = useState<FileEdit[]>([]);
  const [reviewIndex, setReviewIndex] = useState(0);
  const [lineDecisions, setLineDecisions] = useState<Record<string, Record<string, LineDecision>>>({});

  const pendingDiffsRef = useRef(pendingDiffs);
  pendingDiffsRef.current = pendingDiffs;

  const addTabRef = useRef(addTab);
  addTabRef.current = addTab;

  const finalizingPathsRef = useRef<Set<string>>(new Set());

  const addDiffs = useCallback((edits: FileEdit[]) => {
    if (!edits || edits.length === 0) return;
    setPendingDiffs(edits);
    setReviewIndex(0);
    setLineDecisions({});
  }, []);

  const removeDiff = useCallback((path: string) => {
    setPendingDiffs((prev) => {
      const next = prev.filter((d) => d.path !== path);
      return next;
    });
    setLineDecisions((prev) => {
      if (!(path in prev)) return prev;
      const next = { ...prev };
      delete next[path];
      return next;
    });
    setReviewIndex((idx) => Math.min(idx, Math.max(0, pendingDiffsRef.current.length - 2)));
  }, []);

  const persistResolvedDiff = useCallback(async (path: string, decisionsForPath: Record<string, LineDecision>) => {
    if (finalizingPathsRef.current.has(path)) return;
    finalizingPathsRef.current.add(path);
    try {
      const diff = pendingDiffsRef.current.find((d) => d.path === path);
      if (!diff) return;

      const lineDiff = buildLineDiff(diff.old_content, diff.new_content);
      if (!areAllChangesResolved(lineDiff, decisionsForPath)) return;

      const { accepted, rejected } = summarizeDecisions(lineDiff, decisionsForPath);
      const shouldDeleteFile =
        (diff.action === 'delete' && rejected === 0) ||
        (diff.action === 'create' && accepted === 0);

      const resolvedContent = buildResolvedContent(lineDiff, decisionsForPath);

      if (shouldDeleteFile) {
        await fsApi.deletePath(path).catch(() => {});
        setFileContentDirect(path, null);
      } else {
        if (diff.action === 'delete') {
          await fsApi.createFile(path, resolvedContent).catch(async () => {
            await fsApi.putFileContent(path, resolvedContent).catch(() => {});
          });
        } else {
          await fsApi.putFileContent(path, resolvedContent).catch(async () => {
            await fsApi.createFile(path, resolvedContent).catch(() => {});
          });
        }
        setFileContentDirect(path, resolvedContent);
      }

      const remaining = pendingDiffsRef.current.filter((d) => d.path !== path);
      removeDiff(path);

      if (remaining.length === 0 && !shouldDeleteFile) {
        const fileName = path.split('/').pop() || path;
        addTabRef.current(path, fileName);
      }
    } finally {
      finalizingPathsRef.current.delete(path);
    }
  }, [removeDiff, setFileContentDirect]);

  const setLineDecision = useCallback((path: string, changeId: string, decision: LineDecision) => {
    setLineDecisions((prev) => {
      const currentForPath = prev[path] ?? {};
      if (currentForPath[changeId] === decision) return prev;

      const nextForPath = { ...currentForPath, [changeId]: decision };
      const next = { ...prev, [path]: nextForPath };

      const diff = pendingDiffsRef.current.find((d) => d.path === path);
      if (diff) {
        const lineDiff = buildLineDiff(diff.old_content, diff.new_content);
        if (areAllChangesResolved(lineDiff, nextForPath)) {
          queueMicrotask(() => {
            void persistResolvedDiff(path, nextForPath);
          });
        }
      }

      return next;
    });
  }, [persistResolvedDiff]);

  const acceptLine = useCallback((path: string, changeId: string) => {
    setLineDecision(path, changeId, 'accept');
  }, [setLineDecision]);

  const rejectLine = useCallback((path: string, changeId: string) => {
    setLineDecision(path, changeId, 'reject');
  }, [setLineDecision]);

  const acceptDiff = useCallback((path: string) => {
    const diff = pendingDiffsRef.current.find((d) => d.path === path);
    if (!diff) return;
    const lineDiff = buildLineDiff(diff.old_content, diff.new_content);
    if (lineDiff.changes.length === 0) {
      setFileContentDirect(path, diff.new_content);
      const remaining = pendingDiffsRef.current.filter((d) => d.path !== path);
      removeDiff(path);
      if (remaining.length === 0) {
        const fileName = path.split('/').pop() || path;
        addTabRef.current(path, fileName);
      }
      return;
    }
    const decisionsForPath = Object.fromEntries(
      lineDiff.changes.map((c) => [c.id, 'accept' as const]),
    );
    setLineDecisions((prev) => ({ ...prev, [path]: decisionsForPath }));
    void persistResolvedDiff(path, decisionsForPath);
  }, [persistResolvedDiff, removeDiff, setFileContentDirect]);

  const rejectDiff = useCallback(async (path: string) => {
    const diff = pendingDiffsRef.current.find((d) => d.path === path);
    if (!diff) return;
    const lineDiff = buildLineDiff(diff.old_content, diff.new_content);
    if (lineDiff.changes.length === 0) {
      await fsApi.putFileContent(path, diff.old_content ?? '').catch(() => {});
      setFileContentDirect(path, diff.old_content ?? '');
      removeDiff(path);
      return;
    }
    const decisionsForPath = Object.fromEntries(
      lineDiff.changes.map((c) => [c.id, 'reject' as const]),
    );
    setLineDecisions((prev) => ({ ...prev, [path]: decisionsForPath }));
    await persistResolvedDiff(path, decisionsForPath);
  }, [persistResolvedDiff, removeDiff, setFileContentDirect]);

  const acceptAll = useCallback(() => {
    const diffs = pendingDiffsRef.current;
    if (diffs.length === 0) return;
    const nextLineDecisions: Record<string, Record<string, LineDecision>> = {};
    for (const diff of diffs) {
      const lineDiff = buildLineDiff(diff.old_content, diff.new_content);
      if (lineDiff.changes.length > 0) {
        nextLineDecisions[diff.path] = Object.fromEntries(
          lineDiff.changes.map((c) => [c.id, 'accept' as const]),
        );
      }
      setFileContentDirect(diff.path, diff.new_content);
    }
    setLineDecisions(nextLineDecisions);
    setPendingDiffs([]);
    setReviewIndex(0);
    const last = diffs[diffs.length - 1];
    const fileName = last.path.split('/').pop() || last.path;
    addTabRef.current(last.path, fileName);
  }, [setFileContentDirect]);

  const rejectAll = useCallback(async () => {
    const diffs = pendingDiffsRef.current;
    const nextLineDecisions: Record<string, Record<string, LineDecision>> = {};
    let lastNonCreate: FileEdit | null = null;
    for (const diff of diffs) {
      const lineDiff = buildLineDiff(diff.old_content, diff.new_content);
      if (lineDiff.changes.length > 0) {
        nextLineDecisions[diff.path] = Object.fromEntries(
          lineDiff.changes.map((c) => [c.id, 'reject' as const]),
        );
      }
      if (diff.action === 'create') {
        await fsApi.deletePath(diff.path).catch(() => {});
        setFileContentDirect(diff.path, null);
      } else if (diff.action === 'delete' && diff.old_content != null) {
        await fsApi.createFile(diff.path, diff.old_content).catch(() => {});
        setFileContentDirect(diff.path, diff.old_content);
        lastNonCreate = diff;
      } else if (diff.old_content != null) {
        await fsApi.putFileContent(diff.path, diff.old_content).catch(() => {});
        setFileContentDirect(diff.path, diff.old_content);
        lastNonCreate = diff;
      }
    }
    setLineDecisions(nextLineDecisions);
    setPendingDiffs([]);
    setReviewIndex(0);
    if (lastNonCreate) {
      const fileName = lastNonCreate.path.split('/').pop() || lastNonCreate.path;
      addTabRef.current(lastNonCreate.path, fileName);
    }
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
    lineDecisions,
    acceptLine,
    rejectLine,
    acceptAll,
    rejectAll,
  };
}
