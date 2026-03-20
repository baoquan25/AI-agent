'use client';

import { useCallback, useEffect, useMemo, useRef, useLayoutEffect, useState } from 'react';
import dynamic from 'next/dynamic';
import type { FileEdit } from '../../lib/types';
import { buildLineDiff, type LineChange, type LineDecision } from '../../lib/lineDiff';
import { VscChevronLeft, VscChevronRight } from '../../lib/icons';

const DiffEditorLazy = dynamic(
  () => import('@monaco-editor/react').then((m) => {
    const DiffEditor = m.DiffEditor;
    return { default: DiffEditor };
  }),
  {
    ssr: false,
    loading: () => (
      <div className="monaco-editor-wrapper" style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'var(--muted)', fontSize: 13 }}>
        Loading diff editor...
      </div>
    ),
  },
);

function SafeDiffEditor(props: React.ComponentProps<typeof DiffEditorLazy>) {
  const editorRef = useRef<import('monaco-editor').editor.IStandaloneDiffEditor | null>(null);
  const monacoRef = useRef<typeof import('monaco-editor') | null>(null);

  const handleBeforeMount = useCallback((monaco: typeof import('monaco-editor')) => {
    monacoRef.current = monaco;
    props.beforeMount?.(monaco);
  }, [props.beforeMount]);

  const handleMount = useCallback((
    editor: import('monaco-editor').editor.IStandaloneDiffEditor,
    monaco: typeof import('monaco-editor'),
  ) => {
    editorRef.current = editor;
    props.onMount?.(editor, monaco);
  }, [props.onMount]);

  useLayoutEffect(() => {
    return () => {
      const editor = editorRef.current;
      const monaco = monacoRef.current;
      if (editor && monaco) {
        try {
          const tmpOrig = monaco.editor.createModel('', 'text/plain');
          const tmpMod = monaco.editor.createModel('', 'text/plain');
          editor.setModel({ original: tmpOrig, modified: tmpMod });
        } catch { /* already disposed */ }
        try { editor.dispose(); } catch { /* ignore */ }
        editorRef.current = null;
      }
    };
  }, []);

  return <DiffEditorLazy {...props} beforeMount={handleBeforeMount} onMount={handleMount} />;
}

type DiffReviewProps = {
  pendingDiffs: FileEdit[];
  reviewIndex: number;
  onSetReviewIndex: (idx: number) => void;
  lineDecisions: Record<string, Record<string, LineDecision>>;
  onAcceptLine: (path: string, changeId: string) => void;
  onRejectLine: (path: string, changeId: string) => void;
  onAcceptAll: () => void;
  onRejectAll: () => void;
};

type OverlayItem = {
  hunk: LineHunk;
  top: number;
};

type LineHunk = {
  id: string;
  changes: LineChange[];
  startLine: number;
  endLine: number;
  kind: 'add' | 'delete' | 'mixed';
};

function getLanguage(path: string): string {
  const ext = path.split('.').pop()?.toLowerCase() ?? '';
  const map: Record<string, string> = {
    py: 'python', js: 'javascript', ts: 'typescript', tsx: 'typescriptreact',
    jsx: 'javascriptreact', json: 'json', md: 'markdown', css: 'css',
    html: 'html', yaml: 'yaml', yml: 'yaml', sh: 'shell', bash: 'shell',
    sql: 'sql', xml: 'xml', rs: 'rust', go: 'go', java: 'java',
    c: 'c', cpp: 'cpp', h: 'c', hpp: 'cpp', rb: 'ruby', php: 'php',
    toml: 'toml', ini: 'ini', txt: 'plaintext',
  };
  return map[ext] || 'plaintext';
}

function actionLabel(action: string): string {
  switch (action) {
    case 'create': return 'New File';
    case 'delete': return 'Deleted';
    case 'update': return 'Modified';
    default: return action;
  }
}

function actionColor(action: string): string {
  switch (action) {
    case 'create': return 'var(--success)';
    case 'delete': return 'var(--error)';
    case 'update': return 'var(--warning)';
    default: return 'var(--muted)';
  }
}

function changeAnchorLine(change: LineChange): number {
  return change.newLineNumber ?? change.oldLineNumber ?? 1;
}

function buildLineHunks(changes: LineChange[]): LineHunk[] {
  if (changes.length === 0) return [];
  const hunks: LineHunk[] = [];
  let current: LineChange[] = [];
  let lastAnchor = -1;

  const pushCurrent = () => {
    if (current.length === 0) return;
    const anchors = current.map(changeAnchorLine);
    const kinds = new Set(current.map((c) => c.kind));
    hunks.push({
      id: current.map((c) => c.id).join('|'),
      changes: current,
      startLine: Math.min(...anchors),
      endLine: Math.max(...anchors),
      kind: kinds.size === 1 ? current[0].kind : 'mixed',
    });
    current = [];
  };

  for (const change of changes) {
    const anchor = changeAnchorLine(change);
    if (current.length === 0) {
      current = [change];
      lastAnchor = anchor;
      continue;
    }
    if (anchor <= lastAnchor + 1) {
      current.push(change);
      lastAnchor = Math.max(lastAnchor, anchor);
    } else {
      pushCurrent();
      current = [change];
      lastAnchor = anchor;
    }
  }
  pushCurrent();
  return hunks;
}

export function DiffReview({
  pendingDiffs,
  reviewIndex,
  onSetReviewIndex,
  lineDecisions,
  onAcceptLine,
  onRejectLine,
  onAcceptAll,
  onRejectAll,
}: DiffReviewProps) {
  const diff = pendingDiffs[reviewIndex] ?? null;
  const language = useMemo(() => diff ? getLanguage(diff.path) : 'plaintext', [diff?.path]);
  const lineDiff = useMemo(
    () => (diff ? buildLineDiff(diff.old_content, diff.new_content) : null),
    [diff?.path, diff?.old_content, diff?.new_content],
  );
  const enableLineReview = diff?.action === 'update';
  const lineChanges = lineDiff?.changes ?? [];
  const lineHunks = useMemo(() => buildLineHunks(lineChanges), [lineChanges]);
  const [overlayItems, setOverlayItems] = useState<OverlayItem[]>([]);

  const modifiedEditorRef = useRef<import('monaco-editor').editor.IStandaloneCodeEditor | null>(null);
  const overlayDisposablesRef = useRef<Array<{ dispose: () => void }>>([]);

  const clearOverlayListeners = useCallback(() => {
    for (const d of overlayDisposablesRef.current) {
      try { d.dispose(); } catch { /* ignore */ }
    }
    overlayDisposablesRef.current = [];
  }, []);

  const recalcOverlayItems = useCallback(() => {
    const editor = modifiedEditorRef.current;
    if (!enableLineReview || !editor || lineHunks.length === 0) {
      setOverlayItems([]);
      return;
    }
    const model = editor.getModel();
    if (!model) {
      setOverlayItems([]);
      return;
    }

    const maxLine = model.getLineCount();
    const scrollTop = editor.getScrollTop();
    const next: OverlayItem[] = lineHunks.map((hunk) => {
      const rawLine = hunk.startLine;
      const anchorLine = Math.min(Math.max(rawLine, 1), maxLine);
      const top = Math.max(0, editor.getTopForLineNumber(anchorLine) - scrollTop);
      return { hunk, top };
    });
    setOverlayItems(next);
  }, [enableLineReview, lineHunks]);

  const setupOverlayListeners = useCallback(() => {
    clearOverlayListeners();
    const editor = modifiedEditorRef.current;
    if (!editor) {
      setOverlayItems([]);
      return;
    }
    overlayDisposablesRef.current = [
      editor.onDidScrollChange(() => recalcOverlayItems()),
      editor.onDidLayoutChange(() => recalcOverlayItems()),
      editor.onDidChangeModel(() => recalcOverlayItems()),
      editor.onDidChangeModelContent(() => recalcOverlayItems()),
    ];
    recalcOverlayItems();
  }, [clearOverlayListeners, recalcOverlayItems]);

  const beforeMount = useCallback((monaco: typeof import('monaco-editor')) => {
    try {
      monaco.editor.defineTheme('diff-dark', {
        base: 'vs-dark',
        inherit: true,
        rules: [],
        colors: {
          'editor.background': '#000000',
          'editor.foreground': '#cccccc',
          'diffEditor.insertedTextBackground': '#2ea04333',
          'diffEditor.removedTextBackground': '#f8514933',
          'diffEditor.insertedLineBackground': '#2ea04322',
          'diffEditor.removedLineBackground': '#f8514922',
        },
      });
    } catch {
      // theme may already exist
    }
  }, []);

  const handleEditorMount = useCallback((editor: import('monaco-editor').editor.IStandaloneDiffEditor) => {
    modifiedEditorRef.current = editor.getModifiedEditor();
    setupOverlayListeners();
  }, [setupOverlayListeners]);

  useEffect(() => {
    recalcOverlayItems();
  }, [recalcOverlayItems, diff?.path, diff?.old_content, diff?.new_content]);

  useEffect(() => {
    return () => {
      clearOverlayListeners();
      modifiedEditorRef.current = null;
    };
  }, [clearOverlayListeners]);

  if (!diff) return null;

  const goPrev = () => onSetReviewIndex(Math.max(0, reviewIndex - 1));
  const goNext = () => onSetReviewIndex(Math.min(pendingDiffs.length - 1, reviewIndex + 1));

  return (
    <div className="diff-review">
      <div className="diff-review-header">
        <div className="diff-review-nav">
          <span className="diff-review-badge" style={{ background: actionColor(diff.action) }}>
            {actionLabel(diff.action)}
          </span>
          <span className="diff-review-path">{diff.path}</span>
          <span className="diff-review-counter">
            {reviewIndex + 1} / {pendingDiffs.length}
          </span>
          {pendingDiffs.length > 1 && (
            <>
              <button type="button" className="diff-nav-btn" onClick={goPrev} disabled={reviewIndex === 0} title="Previous">
                <VscChevronLeft size={14} />
              </button>
              <button type="button" className="diff-nav-btn" onClick={goNext} disabled={reviewIndex === pendingDiffs.length - 1} title="Next">
                <VscChevronRight size={14} />
              </button>
            </>
          )}
        </div>
        <div className="diff-review-actions">
          <button type="button" className="diff-btn diff-btn-reject-all" onClick={onRejectAll}>
            Reject All
          </button>
          <button type="button" className="diff-btn diff-btn-accept-all" onClick={onAcceptAll}>
            Accept All
          </button>
        </div>
      </div>
      <div className="diff-review-editor">
        <SafeDiffEditor
          key={diff.path}
          height="100%"
          language={language}
          original={diff.old_content ?? ''}
          modified={diff.new_content ?? ''}
          theme="diff-dark"
          beforeMount={beforeMount}
          onMount={handleEditorMount}
          options={{
            readOnly: true,
            renderSideBySide: false,
            minimap: { enabled: false },
            fontSize: 14,
            fontFamily: "'JetBrains Mono', 'Cascadia Code', Consolas, Menlo, Monaco, 'Courier New', monospace",
            fontLigatures: true,
            lineHeight: 22,
            scrollBeyondLastLine: false,
            automaticLayout: true,
            renderOverviewRuler: false,
            enableSplitViewResizing: false,
            originalEditable: false,
            padding: { top: 8 },
          }}
        />
        {enableLineReview && (
          <div className="diff-line-overlay">
            {overlayItems.map(({ hunk, top }) => {
              const decisionsForPath = lineDecisions[diff.path] ?? {};
              const acceptedCount = hunk.changes.filter((c) => decisionsForPath[c.id] === 'accept').length;
              const rejectedCount = hunk.changes.filter((c) => decisionsForPath[c.id] === 'reject').length;
              const fullyAccepted = acceptedCount === hunk.changes.length;
              const fullyRejected = rejectedCount === hunk.changes.length;
              const sign = hunk.kind === 'add' ? '+' : hunk.kind === 'delete' ? '-' : '~';

              const acceptHunk = () => {
                for (const change of hunk.changes) onAcceptLine(diff.path, change.id);
              };

              const rejectHunk = () => {
                for (const change of hunk.changes) onRejectLine(diff.path, change.id);
              };

              return (
                <div
                  key={hunk.id}
                  className={`diff-line-overlay-item diff-line-overlay-item-${hunk.kind}`}
                  style={{ top: `${top}px` }}
                >
                  <span className="diff-line-overlay-label">
                    {sign}
                  </span>
                  <div className="diff-line-overlay-actions">
                    <button
                      type="button"
                      className={`diff-line-btn diff-line-btn-reject${fullyRejected ? ' active' : ''}`}
                      onClick={rejectHunk}
                    >
                      Reject
                    </button>
                    <button
                      type="button"
                      className={`diff-line-btn diff-line-btn-accept${fullyAccepted ? ' active' : ''}`}
                      onClick={acceptHunk}
                    >
                      Accept
                    </button>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}
