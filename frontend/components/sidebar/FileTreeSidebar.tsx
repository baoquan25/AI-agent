'use client';

import React from 'react';
import { FileTree } from './FileTree';
import { SearchPanel } from './SearchPanel';

type FileTreeSidebarProps = {
  width: number;
  sidebarTab: 'files' | 'search';
  setSidebarTab: (tab: 'files' | 'search') => void;
  openSearchTab: () => void;
  searchPattern: string;
  setSearchPattern: (v: string) => void;
  searchResults: string[];
  searchInputRef: React.RefObject<HTMLInputElement | null>;
  fileTreeData: unknown;
  expandedFolders: Set<string>;
  selectedTreePath: string | null;
  treeCreateMode: 'file' | 'folder' | null;
  treeCreateParentPath: string;
  treeCreateBeforePath: string | null;
  treeCreateInput: string;
  renameNode: unknown;
  renameValue: string;
  initialExpandDoneRef: React.MutableRefObject<boolean>;
  openTabs: { path: string; name: string }[];
  chatLoading: boolean;
  modifiedCount: number;
  loadFileTree: () => void;
  toolbarNewFile: () => void;
  toolbarNewFolder: () => void;
  saveAllFiles: () => void;
  toggleFolder: (path: string) => void;
  setSelectedTreePath: (path: string | null) => void;
  setSelectedFolder: (path: string | null) => void;
  setContextMenu: React.Dispatch<React.SetStateAction<{ show: boolean; x: number; y: number; node: import('../../lib/types').TreeNode | null; showNewFile: boolean; showNewFolder: boolean; showCopy: boolean; showPaste: boolean }>>;
  hasCopied: boolean;
  setTreeCreateInput: (v: string) => void;
  setRenameValue: (v: string) => void;
  onRenameBlur: () => void;
  onRenameKeyDown: (e: React.KeyboardEvent) => void;
  onCreateBlur: () => void;
  onCreateKeyDown: (e: React.KeyboardEvent) => void;
  treeCreateInputRef: React.RefObject<HTMLInputElement | null>;
  renameInputRef: React.RefObject<HTMLInputElement | null>;
  addTab: (path: string, name: string) => void;
  switchTab: (path: string) => void;
  loadFileContent: (path: string) => Promise<void>;
};

export function FileTreeSidebar(props: FileTreeSidebarProps) {
  const {
    width,
    sidebarTab,
    setSidebarTab,
    openSearchTab,
    searchPattern,
    setSearchPattern,
    searchResults,
    searchInputRef,
    fileTreeData,
    expandedFolders,
    selectedTreePath,
    treeCreateMode,
    treeCreateParentPath,
    treeCreateBeforePath,
    treeCreateInput,
    renameNode,
    renameValue,
    initialExpandDoneRef,
    openTabs,
    chatLoading,
    modifiedCount,
    loadFileTree,
    toolbarNewFile,
    toolbarNewFolder,
    saveAllFiles,
    toggleFolder,
    setSelectedTreePath,
    setSelectedFolder,
    setContextMenu,
    hasCopied,
    setTreeCreateInput,
    setRenameValue,
    onRenameBlur,
    onRenameKeyDown,
    onCreateBlur,
    onCreateKeyDown,
    treeCreateInputRef,
    renameInputRef,
    addTab,
    switchTab,
    loadFileContent,
  } = props;

  return (
    <div style={{ width, minWidth: 80, flexShrink: 0, display: 'flex', flexDirection: 'column' }}>
      <div className="section" id="fileTreeSection">
        <div className="sidebar-toolbar">
          <button
            type="button"
            className={`sidebar-tab ${sidebarTab === 'files' ? 'active' : ''}`}
            onClick={() => setSidebarTab('files')}
            title="Files"
          >
            <span className="codicon codicon-files" />
          </button>
          <button
            type="button"
            className={`sidebar-tab ${sidebarTab === 'search' ? 'active' : ''}`}
            onClick={() => {
              openSearchTab();
            }}
            title="Search (Ctrl+P)"
          >
            <span className="codicon codicon-search" />
          </button>
        </div>
        {sidebarTab === 'files' && (
          <FileTree
            fileTreeData={fileTreeData as import('../../lib/types').TreeNode | null}
            expandedFolders={expandedFolders}
            selectedTreePath={selectedTreePath}
            treeCreateMode={treeCreateMode}
            treeCreateParentPath={treeCreateParentPath}
            treeCreateBeforePath={treeCreateBeforePath}
            treeCreateInput={treeCreateInput}
            renameNode={renameNode as { node: import('../../lib/types').TreeNode; path: string } | null}
            renameValue={renameValue}
            initialExpandDoneRef={initialExpandDoneRef}
            openTabs={openTabs}
            chatLoading={chatLoading}
            modifiedCount={modifiedCount}
            onLoadFileTree={loadFileTree}
            onToolbarNewFile={toolbarNewFile}
            onToolbarNewFolder={toolbarNewFolder}
            onSaveAllFiles={saveAllFiles}
            onToggleFolder={toggleFolder}
            setTreeCreateInput={setTreeCreateInput}
            setRenameValue={setRenameValue}
            onRenameBlur={onRenameBlur}
            onRenameKeyDown={onRenameKeyDown}
            onCreateBlur={onCreateBlur}
            onCreateKeyDown={onCreateKeyDown}
            treeCreateInputRef={treeCreateInputRef}
            renameInputRef={renameInputRef}
            setSelectedTreePath={setSelectedTreePath}
            setSelectedFolder={setSelectedFolder}
            setContextMenu={setContextMenu}
            hasCopied={hasCopied}
            addTab={addTab}
            switchTab={switchTab}
            loadFileContent={loadFileContent}
          />
        )}
        {sidebarTab === 'search' && (
          <SearchPanel
            searchPattern={searchPattern}
            onSearchPatternChange={setSearchPattern}
            searchResults={searchResults}
            searchInputRef={searchInputRef}
            chatLoading={chatLoading}
            openTabs={openTabs}
            onResultClick={(path) => {
              loadFileContent(path);
              addTab(path, path.split('/').pop() || path);
            }}
            switchTab={switchTab}
          />
        )}
      </div>
    </div>
  );
}
