'use client';

import type { TabItem } from '../../lib/types';
import { getFileIcon, VscClose } from '../../lib/icons';

type EditorTabsProps = {
  openTabs: TabItem[];
  currentFilePath: string | null;
  fileCache: Record<string, { content: string; modified: boolean }>;
  onSwitchTab: (path: string) => void;
  onCloseTab: (path: string) => void;
};

export function EditorTabs({ openTabs, currentFilePath, fileCache, onSwitchTab, onCloseTab }: EditorTabsProps) {
  return (
    <div className="editor-tabs">
      {openTabs.map((tab) => {
        const cached = fileCache[tab.path];
        const isModified = cached?.modified;
        const { Icon: FileIcon, color: fileIconColor } = getFileIcon(tab.name);
        return (
          <div
            key={tab.path}
            className={`editor-tab ${tab.path === currentFilePath ? 'active' : ''}`}
            title={tab.path}
            onClick={() => onSwitchTab(tab.path)}
            onAuxClick={(e) => {
              if (e.button === 1) {
                e.preventDefault();
                onCloseTab(tab.path);
              }
            }}
          >
            <span style={{ flexShrink: 0, color: fileIconColor, display: 'inline-flex' }}>
              <FileIcon size={12} />
            </span>
            <span className="tab-name">{tab.name}</span>
            <span
              className="tab-close"
              onClick={(e) => { e.stopPropagation(); onCloseTab(tab.path); }}
              title={isModified ? 'Chưa lưu (trỏ vào để đóng)' : undefined}
            >
              {isModified && <span className="tab-unsaved-dot">●</span>}
              <span className="tab-close-icon"><VscClose size={14} /></span>
            </span>
          </div>
        );
      })}
    </div>
  );
}
