'use client';

import { useCallback } from 'react';
import Editor from '@monaco-editor/react';
import type { editor } from 'monaco-editor';

type CodeAreaProps = {
  value: string;
  onChange: (value: string) => void;
  readOnly: boolean;
  language?: string;
  onRun: () => void;
  chatLoading: boolean;
};

export function CodeArea({ value, onChange, readOnly, language = 'python', onRun, chatLoading }: CodeAreaProps) {
  const beforeMount = useCallback((monaco: typeof import('monaco-editor')) => {
    monaco.editor.defineTheme('app-black', {
      base: 'vs-dark',
      inherit: true,
      rules: [],
      colors: {
        'editor.background': '#000000',
        'editor.foreground': '#cccccc',
        'editorLineNumber.foreground': '#888888',
        'editorLineNumber.activeForeground': '#cccccc',
        'editorCursor.foreground': '#cccccc',
        'editor.selectionBackground': '#264f78',
        'editor.inactiveSelectionBackground': '#3a3d41',
        'editor.lineHighlightBackground': '#1a1a1a',
      },
    });
  }, []);

  const handleMount = useCallback(
    (ed: editor.IStandaloneCodeEditor) => {
      import('monaco-editor').then((monaco) => {
        ed.addCommand(
          monaco.KeyMod.CtrlCmd | monaco.KeyCode.Enter,
          () => {
            if (!chatLoading) onRun();
          }
        );
      });
    },
    [onRun, chatLoading]
  );

  return (
    <div className="monaco-editor-wrapper">
      <Editor
        height="100%"
        defaultLanguage={language}
        language={language}
        value={value}
        onChange={(v) => onChange(v ?? '')}
        theme="app-black"
        options={{
          readOnly,
          minimap: { enabled: true },
          fontSize: 14,
          fontFamily: "'JetBrains Mono', 'Cascadia Code', Consolas, Menlo, Monaco, 'Courier New', monospace",
          fontLigatures: true,
          fontWeight: '400',
          lineHeight: 22,
          wordWrap: 'on',
          tabSize: 4,
          padding: { top: 16 },
          scrollBeyondLastLine: false,
          automaticLayout: true,
          lineNumbersMinChars: 2,
          glyphMargin: false,
        }}
        beforeMount={beforeMount}
        onMount={handleMount}
      />
    </div>
  );
}
