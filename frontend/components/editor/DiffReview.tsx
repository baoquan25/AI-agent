'use client';

import { useCallback, useMemo, useRef, useLayoutEffect } from 'react';
import dynamic from 'next/dynamic';
import type { FileEdit } from '../../lib/types';

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

  const handleMount = useCallback((editor: import('monaco-editor').editor.IStandaloneDiffEditor) => {
    editorRef.current = editor;
  }, []);

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
  onAccept: (path: string) => void;
  onReject: (path: string) => void;
  onAcceptAll: () => void;
  onRejectAll: () => void;
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

export function DiffReview({
  pendingDiffs,
  reviewIndex,
  onSetReviewIndex,
  onAccept,
  onReject,
  onAcceptAll,
  onRejectAll,
}: DiffReviewProps) {
  const diff = pendingDiffs[reviewIndex] ?? null;
  const language = useMemo(() => diff ? getLanguage(diff.path) : 'plaintext', [diff?.path]);

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
                <span className="codicon codicon-chevron-left" />
              </button>
              <button type="button" className="diff-nav-btn" onClick={goNext} disabled={reviewIndex === pendingDiffs.length - 1} title="Next">
                <span className="codicon codicon-chevron-right" />
              </button>
            </>
          )}
        </div>
        <div className="diff-review-actions">
          {pendingDiffs.length > 1 && (
            <>
              <button type="button" className="diff-btn diff-btn-reject-all" onClick={onRejectAll}>
                Reject All
              </button>
              <button type="button" className="diff-btn diff-btn-accept-all" onClick={onAcceptAll}>
                Accept All
              </button>
            </>
          )}
          <button type="button" className="diff-btn diff-btn-reject" onClick={() => onReject(diff.path)}>
            Reject
          </button>
          <button type="button" className="diff-btn diff-btn-accept" onClick={() => onAccept(diff.path)}>
            Accept
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
      </div>
    </div>
  );
}

