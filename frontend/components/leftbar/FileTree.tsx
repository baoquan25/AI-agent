'use client';

import type { TreeNode } from '../../lib/types';
import { VscNewFile, VscNewFolder, VscRefresh, VscSaveAll } from '../../lib/icons';
import { TreeInlineCreate } from './TreeInlineCreate';
import { FileTreeNode } from './FileTreeNode';

type FileTreeProps = {
  fileTreeData: TreeNode | null;
  expandedFolders: Set<string>;
  selectedTreePath: string | null;
  treeCreateMode: 'file' | 'folder' | null;
  treeCreateParentPath: string;
  treeCreateBeforePath: string | null;
  treeCreateInput: string;
  renameNode: { node: TreeNode; path: string } | null;
  renameValue: string;
  initialExpandDoneRef: React.MutableRefObject<boolean>;
  openTabs: { path: string; name: string }[];
  chatLoading: boolean;
  modifiedCount: number;
  onLoadFileTree: () => void;
  onToolbarNewFile: () => void;
  onToolbarNewFolder: () => void;
  onSaveAllFiles: () => void;
  onToggleFolder: (path: string) => void;
  setTreeCreateInput: (v: string) => void;
  setRenameValue: (v: string) => void;
  onRenameBlur: () => void;
  onRenameKeyDown: (e: React.KeyboardEvent) => void;
  onCreateBlur: () => void;
  onCreateKeyDown: (e: React.KeyboardEvent) => void;
  treeCreateInputRef: React.RefObject<HTMLInputElement | null>;
  renameInputRef: React.RefObject<HTMLInputElement | null>;
  setSelectedTreePath: (path: string | null) => void;
  setSelectedFolder: (path: string | null) => void;
  setContextMenu: (state: { show: boolean; x: number; y: number; node: TreeNode | null; showNewFile: boolean; showNewFolder: boolean; showCopy: boolean; showPaste: boolean }) => void;
  hasCopied: boolean;
  addTab: (path: string, name: string) => void;
  switchTab: (path: string) => void;
  loadFileContent: (path: string) => Promise<void>;
};

export function FileTree(props: FileTreeProps) {
  const {
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
    onLoadFileTree,
    onToolbarNewFile,
    onToolbarNewFolder,
    onSaveAllFiles,
  onToggleFolder,
  setTreeCreateInput,
    setRenameValue,
    onRenameBlur,
    onRenameKeyDown,
    onCreateBlur,
    onCreateKeyDown,
    treeCreateInputRef,
    renameInputRef,
    setSelectedTreePath,
    setSelectedFolder,
    setContextMenu,
    hasCopied,
    addTab,
    switchTab,
    loadFileContent,
  } = props;

  const renderInlineCreate = (level: number) => (
    <TreeInlineCreate
      level={level}
      mode={treeCreateMode === 'file' ? 'file' : 'folder'}
      value={treeCreateInput}
      onChange={setTreeCreateInput}
      onBlur={onCreateBlur}
      onKeyDown={onCreateKeyDown}
      inputRef={treeCreateInputRef}
    />
  );

  const handleSelect = (path: string, isDir: boolean, node: TreeNode) => {
    setSelectedTreePath(path);
    if (isDir) setSelectedFolder(path);
    else setSelectedFolder(path ? path.split('/').slice(0, -1).join('/') : '');
    if (chatLoading) {
      if (!isDir && openTabs.some((t) => t.path === path)) switchTab(path);
    } else {
      if (!isDir) {
        addTab(path, node.name);
        loadFileContent(path);
      } else onToggleFolder(path);
    }
  };

  const handleContextMenu = (e: React.MouseEvent, node: TreeNode) => {
    if (chatLoading) return;
    e.preventDefault();
    setContextMenu({ show: true, x: e.clientX, y: e.clientY, node, showNewFile: true, showNewFolder: true, showCopy: true, showPaste: hasCopied });
  };

  const treeContent = !fileTreeData || !fileTreeData.children?.length ? (
    <div className="tree-empty">{fileTreeData === null ? 'Failed to load' : 'No files yet'}</div>
  ) : (
    fileTreeData.children.map((node) => {
      const nodePath = node.path || node.name;
      const showCreateBefore = treeCreateMode && treeCreateParentPath === '' && treeCreateBeforePath === nodePath;
      return (
        <div key={nodePath}>
          {showCreateBefore && renderInlineCreate(0)}
          <FileTreeNode
            node={node}
            level={0}
            firstLevel={true}
            expandedFolders={expandedFolders}
            selectedTreePath={selectedTreePath}
            renameNode={renameNode}
            renameValue={renameValue}
            treeCreateMode={treeCreateMode}
            treeCreateParentPath={treeCreateParentPath}
            treeCreateBeforePath={treeCreateBeforePath}
            treeCreateInput={treeCreateInput}
            initialExpandDone={initialExpandDoneRef.current}
            openTabs={openTabs}
            chatLoading={chatLoading}
            onToggleFolder={onToggleFolder}
            onSelect={handleSelect}
            onContextMenu={handleContextMenu}
            onRenameChange={setRenameValue}
            onRenameBlur={onRenameBlur}
            onRenameKeyDown={onRenameKeyDown}
            onCreateBlur={onCreateBlur}
            onCreateKeyDown={onCreateKeyDown}
            setTreeCreateInput={setTreeCreateInput}
            treeCreateInputRef={treeCreateInputRef}
            renameInputRef={renameInputRef}
            renderInlineCreate={renderInlineCreate}
          />
        </div>
      );
    })
  );

  return (
    <div className="file-tree-section">
      <div className="file-tree-header">
        <span className="file-tree-title">WORKSPACE</span>
        <div className="file-tree-actions">
          <button type="button" className="icon-btn" onClick={onToolbarNewFile} title="New File" disabled={chatLoading}>
            <VscNewFile size={16} />
          </button>
          <button type="button" className="icon-btn" onClick={onToolbarNewFolder} title="New Folder" disabled={chatLoading}>
            <VscNewFolder size={16} />
          </button>
          <button type="button" className="icon-btn" onClick={onLoadFileTree} title="Refresh" disabled={chatLoading}>
            <VscRefresh size={16} />
          </button>
          <button
            type="button"
            className="icon-btn"
            onClick={onSaveAllFiles}
            disabled={chatLoading}
            title={modifiedCount > 0 ? `Save All (${modifiedCount} unsaved)` : 'Save All (Ctrl+S)'}
          >
            <VscSaveAll size={16} />
          </button>
        </div>
      </div>
      <div id="fileTree">
        {treeCreateMode && treeCreateParentPath === '' && !treeCreateBeforePath && renderInlineCreate(0)}
        {treeContent}
      </div>
    </div>
  );
}
