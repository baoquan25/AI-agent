'use client';

import dynamic from 'next/dynamic';
import type { TabItem } from '../../lib/types';
import { EditorTabs } from './EditorTabs';

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
  } = props;

  return (
    <div className="section" id="editorSection" style={{ flex: `${editorFlex} 0 0` }}>
        {openTabs.length > 0 && (
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
                  <span className="codicon codicon-play" />
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
        )}
    </div>
  );
}
