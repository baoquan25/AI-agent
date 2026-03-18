'use client';

import dynamic from 'next/dynamic';
import type { TabItem, FileEdit } from '../../lib/types';
import { VscPlay } from '../../lib/icons';
import { EditorTabs } from './EditorTabs';
import { DiffReview } from './DiffReview';

const CodeArea = dynamic(() => import('./CodeArea').then((m) => m.CodeArea), {
  ssr: false,
  loading: () => <div className="monaco-editor-wrapper" style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'var(--muted)', fontSize: 13 }}>Loading editor...</div>,
});

type EditorSectionProps = {
  editorFlex: number;
  openTabs: TabItem[];
  currentFilePath: string | null;
  fileCache: Record<string, { content: string; modified: boolean }>;
  codeValue: string;
  onCodeChange: (value: string) => void;
  runBusy: boolean;
  chatLoading: boolean;
  onSwitchTab: (path: string) => void;
  onCloseTab: (path: string) => void;
  onRun: () => void;
  pendingDiffs: FileEdit[];
  reviewIndex: number;
  onSetReviewIndex: (idx: number) => void;
  onAcceptDiff: (path: string) => void;
  onRejectDiff: (path: string) => void;
  onAcceptAll: () => void;
  onRejectAll: () => void;
};

export function EditorSection(props: EditorSectionProps) {
  const {
    editorFlex,
    openTabs,
    currentFilePath,
    fileCache,
    codeValue,
    onCodeChange,
    runBusy,
    chatLoading,
    onSwitchTab,
    onCloseTab,
    onRun,
    pendingDiffs,
    reviewIndex,
    onSetReviewIndex,
    onAcceptDiff,
    onRejectDiff,
    onAcceptAll,
    onRejectAll,
  } = props;

  const showDiffReview = pendingDiffs.length > 0;

  return (
    <div className="section" id="editorSection" style={{ flex: `${editorFlex} 0 0` }}>
        {showDiffReview ? (
          <DiffReview
            pendingDiffs={pendingDiffs}
            reviewIndex={reviewIndex}
            onSetReviewIndex={onSetReviewIndex}
            onAccept={onAcceptDiff}
            onReject={onRejectDiff}
            onAcceptAll={onAcceptAll}
            onRejectAll={onRejectAll}
          />
        ) : openTabs.length > 0 ? (
          <>
            <div className="editor-tabs-bar">
              <EditorTabs
                openTabs={openTabs}
                currentFilePath={currentFilePath}
                fileCache={fileCache}
                onSwitchTab={onSwitchTab}
                onCloseTab={onCloseTab}
              />
              <div className="actions">
                <button
                  type="button"
                  className="btn-run"
                  onClick={onRun}
                  disabled={runBusy || chatLoading}
                  title={runBusy ? 'Running...' : 'Run'}
                >
                  <div className="spinner" style={{ display: runBusy ? 'inline-block' : 'none' }} />
                  <VscPlay size={16} />
                </button>
              </div>
            </div>
            <CodeArea
              value={codeValue}
              onChange={onCodeChange}
              readOnly={chatLoading}
              language={currentFilePath?.toLowerCase().endsWith('.py') ? 'python' : 'plaintext'}
              onRun={onRun}
              chatLoading={chatLoading}
            />
          </>
        ) : null}
    </div>
  );
}
