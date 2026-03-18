'use client';

import { VscClose } from '../../lib/icons';
import { OutputPanel } from './OutputPanel';
import { TerminalPanel } from './TerminalPanel';

type OutputSectionProps = {
  editorFlex: number;
  outputTab: 'output' | 'terminal';
  outputHtml: string;
  terminalError: string | null;
  terminalContainerRef: React.RefObject<HTMLDivElement | null>;
  setTerminalError: (msg: string | null) => void;
  onOutputTab: () => void;
  onTerminalTab: () => void;
  onClosePanel?: () => void;
};

export function OutputSection(props: OutputSectionProps) {
  const {
    editorFlex,
    outputTab,
    outputHtml,
    terminalError,
    terminalContainerRef,
    setTerminalError,
    onOutputTab,
    onTerminalTab,
    onClosePanel,
  } = props;

  const isClosed = editorFlex >= 100;

  return (
    <>
      <div
        className={`section ${isClosed ? 'output-section-closed' : ''}`}
        id="outputSection"
        style={{ flex: `${100 - editorFlex} 0 0`, display: 'flex', flexDirection: 'column' }}
      >
        <div className="output-tabs-bar">
          <div className="output-tabs">
            <button type="button" className={`output-tab ${outputTab === 'output' ? 'active' : ''}`} onClick={onOutputTab}>Output</button>
            <button type="button" className={`output-tab ${outputTab === 'terminal' ? 'active' : ''}`} onClick={onTerminalTab}>Terminal</button>
          </div>
          {onClosePanel && (
            <button type="button" className="output-panel-close" onClick={onClosePanel} title="Đóng panel (Ctrl+J)" aria-label="Đóng panel">
              <VscClose size={14} />
            </button>
          )}
        </div>
        <OutputPanel html={outputHtml} visible={outputTab === 'output'} />
        <TerminalPanel active={outputTab === 'terminal'} error={terminalError} containerRef={terminalContainerRef} onError={setTerminalError} />
      </div>
    </>
  );
}
