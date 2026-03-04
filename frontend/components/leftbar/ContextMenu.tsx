'use client';

import type { TreeNode } from '../../lib/types';

type ContextMenuState = {
  show: boolean;
  x: number;
  y: number;
  node: TreeNode | null;
  showNewFile: boolean;
  showNewFolder: boolean;
  showCopy: boolean;
  showPaste: boolean;
};

type ContextMenuProps = {
  menu: ContextMenuState;
  menuRef: React.RefObject<HTMLDivElement | null>;
  onAction: (action: 'newFile' | 'newFolder' | 'rename' | 'delete' | 'copy' | 'paste') => void;
};

export function ContextMenu({ menu, menuRef, onAction }: ContextMenuProps) {
  return (
    <div
      ref={menuRef as React.RefObject<HTMLDivElement>}
      className="context-menu"
      style={{ display: menu.show ? 'block' : 'none', left: menu.x, top: menu.y }}
    >
      {menu.showNewFile && <div className="context-menu-item" onClick={() => onAction('newFile')}>New File...</div>}
      {menu.showNewFolder && <div className="context-menu-item" onClick={() => onAction('newFolder')}>New Folder...</div>}
      {menu.showCopy && <div className="context-menu-item" onClick={() => onAction('copy')}>Copy</div>}
      {menu.showPaste && <div className="context-menu-item" onClick={() => onAction('paste')}>Paste</div>}
      <div className="context-menu-item" onClick={() => onAction('rename')}>Rename...</div>
      <div className="context-menu-item" onClick={() => onAction('delete')}>Delete permanently</div>
    </div>
  );
}
