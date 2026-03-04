'use client';

import type { TreeNode } from '../../lib/types';
import { formatFileSize } from '../../lib/utils';
import { TreeInlineCreate } from './TreeInlineCreate';

type FileTreeNodeProps = {
  node: TreeNode;
  level: number;
  firstLevel: boolean;
  expandedFolders: Set<string>;
  selectedTreePath: string | null;
  renameNode: { node: TreeNode; path: string } | null;
  renameValue: string;
  treeCreateMode: 'file' | 'folder' | null;
  treeCreateParentPath: string;
  treeCreateBeforePath: string | null;
  treeCreateInput: string;
  initialExpandDone: boolean;
  openTabs: { path: string }[];
  chatLoading: boolean;
  onToggleFolder: (path: string) => void;
  onSelect: (path: string, isDir: boolean, node: TreeNode) => void;
  onContextMenu: (e: React.MouseEvent, node: TreeNode) => void;
  onRenameChange: (value: string) => void;
  onRenameBlur: () => void;
  onRenameKeyDown: (e: React.KeyboardEvent) => void;
  onCreateBlur: () => void;
  onCreateKeyDown: (e: React.KeyboardEvent) => void;
  setTreeCreateInput: (v: string) => void;
  treeCreateInputRef: React.RefObject<HTMLInputElement | null>;
  renameInputRef: React.RefObject<HTMLInputElement | null>;
  renderInlineCreate: (level: number) => React.ReactNode;
};

export function FileTreeNode(props: FileTreeNodeProps) {
  const {
    node,
    level,
    firstLevel,
    expandedFolders,
    selectedTreePath,
    renameNode,
    renameValue,
    treeCreateMode,
    treeCreateParentPath,
    treeCreateBeforePath,
    treeCreateInput,
    initialExpandDone,
    openTabs,
    chatLoading,
    onToggleFolder,
    onSelect,
    onContextMenu,
    onRenameChange,
    onRenameBlur,
    onRenameKeyDown,
    onCreateBlur,
    onCreateKeyDown,
    setTreeCreateInput,
    treeCreateInputRef,
    renameInputRef,
    renderInlineCreate,
  } = props;

  const path = node.path || node.name;
  const isDir = node.type === 'directory';
  const hasChildren = isDir && node.children && node.children.length > 0;
  const shouldExpand = isDir && (expandedFolders.has(path) || (firstLevel && !initialExpandDone));
  const isPy = node.type === 'file' && node.name.toLowerCase().endsWith('.py');
  const paddingLeft = 8 + level * 8;

  const leadIcon = isDir ? (
    shouldExpand ? (
      <span className="tree-lead-icon codicon codicon-chevron-down" onClick={(e) => { e.stopPropagation(); onToggleFolder(path); }} title="Thu gọn" />
    ) : (
      <span className="tree-lead-icon codicon codicon-chevron-right" onClick={(e) => { e.stopPropagation(); onToggleFolder(path); }} title="Mở rộng" />
    )
  ) : isPy ? (
    <span className="tree-lead-icon codicon codicon-python" />
  ) : (
    <span className="tree-lead-icon codicon codicon-file" />
  );

  if (renameNode?.path === path) {
    return (
      <div key={path} className="tree-item" style={{ paddingLeft }}>
        <div className="tree-item-content">
          {leadIcon}
          <input
            ref={renameInputRef as React.RefObject<HTMLInputElement>}
            type="text"
            className="tree-inline-input"
            value={renameValue}
            onChange={(e) => onRenameChange(e.target.value)}
            onBlur={onRenameBlur}
            onKeyDown={onRenameKeyDown}
          />
        </div>
      </div>
    );
  }

  return (
    <div key={path}>
      <div
        className={`tree-item ${path === selectedTreePath ? 'selected' : ''}`}
        style={{ paddingLeft }}
        onClick={() => {
          onSelect(path, isDir, node);
        }}
        onContextMenu={(e) => onContextMenu(e, node)}
      >
        <div className="tree-item-content">
          {leadIcon}
          <span className="tree-item-name">{node.name}</span>
          {node.size != null && <span className="tree-item-size">{formatFileSize(node.size)}</span>}
        </div>
      </div>
      {(hasChildren || (path === treeCreateParentPath && treeCreateMode) || (isDir && shouldExpand)) && (
        <div className="tree-children" style={{ display: shouldExpand ? 'block' : 'none' }}>
          {path === treeCreateParentPath && treeCreateMode && !treeCreateBeforePath && renderInlineCreate(level + 1)}
          {node.children?.map((child) => {
            const childPath = child.path || child.name;
            const showCreateBefore = path === treeCreateParentPath && treeCreateMode && treeCreateBeforePath === childPath;
            return (
              <div key={childPath}>
                {showCreateBefore && renderInlineCreate(level + 1)}
                <FileTreeNode
                  {...props}
                  node={child}
                  level={level + 1}
                  firstLevel={false}
                />
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
