'use client';

import { useState, useEffect, useCallback, useRef } from 'react';
import type { TreeNode } from '../lib/types';
import * as fsApi from '../lib/api/fs';
import type { ListFileItem } from '../lib/api/fs';

const REFRESH_DEBOUNCE_MS = 250;

function getNodePath(node: TreeNode, parentPath: string): string {
  return node.path ?? (parentPath ? `${parentPath}/${node.name}` : node.name);
}

function insertNodeIntoTree(tree: TreeNode | null, parentPath: string, node: TreeNode): TreeNode | null {
  if (!tree) return null;
  const normParent = (parentPath || '').replace(/^\/+|\/+$/g, '');
  const pathMatch = (p: string) => (p || '').replace(/^\/+|\/+$/g, '') === normParent;

  function go(n: TreeNode, parent: string): TreeNode {
    const np = getNodePath(n, parent);
    if (pathMatch(np)) {
      const children = [...(n.children ?? [])];
      const existing = children.findIndex((c) => (c.path ?? `${np}/${c.name}`) === node.path);
      if (existing >= 0) children[existing] = node;
      else children.push(node);
      children.sort((a, b) => (a.type === b.type ? (a.name < b.name ? -1 : 1) : a.type === 'directory' ? -1 : 1));
      return { ...n, children };
    }
    return { ...n, children: (n.children ?? []).map((c) => go(c, np)) };
  }
  return go(tree, '');
}

function removeNodeFromTree(tree: TreeNode | null, path: string): TreeNode | null {
  if (!tree) return null;
  const norm = (path || '').replace(/^\/+|\/+$/g, '');
  const isDescendant = (p: string) => p === norm || p.startsWith(norm + '/');

  function go(n: TreeNode, parent: string): TreeNode | null {
    const np = getNodePath(n, parent);
    if (isDescendant(np)) return null;
    const children = (n.children ?? []).map((c) => go(c, np)).filter((c): c is TreeNode => c != null);
    return { ...n, children };
  }
  return go(tree, '');
}

function mergeListIntoTree(tree: TreeNode | null, folderPath: string, items: ListFileItem[]): TreeNode | null {
  if (!tree) return null;
  const normFolder = (folderPath || '').replace(/^\/+|\/+$/g, '');
  const pathMatch = (p: string) => (p || '').replace(/^\/+|\/+$/g, '') === normFolder;

  function go(n: TreeNode, parent: string): TreeNode {
    const np = getNodePath(n, parent);
    if (pathMatch(np)) {
      const children: TreeNode[] = items.map((f) => ({
        type: f.type as 'file' | 'directory',
        name: f.name,
        path: f.path,
        ...(f.size != null && { size: f.size }),
      }));
      children.sort((a, b) => (a.type === b.type ? (a.name < b.name ? -1 : 1) : a.type === 'directory' ? -1 : 1));
      return { ...n, children };
    }
    return { ...n, children: (n.children ?? []).map((c) => go(c, np)) };
  }
  return go(tree, '');
}

function renameNodeInTree(tree: TreeNode | null, oldPath: string, newPath: string): TreeNode | null {
  if (!tree) return null;
  const normOld = (oldPath || '').replace(/^\/+|\/+$/g, '');
  const normNew = (newPath || '').replace(/^\/+|\/+$/g, '');
  const newName = normNew.split('/').pop() ?? normNew;

  function go(n: TreeNode, parent: string): TreeNode {
    const np = getNodePath(n, parent);
    const updatedPath = np === normOld ? normNew : np.startsWith(normOld + '/') ? np.replace(normOld, normNew) : np;
    const updatedName = np === normOld ? newName : n.name;
    const children = (n.children ?? []).map((c) => go(c, np));
    return { ...n, name: updatedName, path: updatedPath, children };
  }
  return go(tree, '');
}

type TabItem = { path: string; name: string };
type FileCacheItem = { content: string; modified: boolean };

export function useFileTree(
  openTabs: TabItem[],
  currentFilePath: string | null,
  setOpenTabs: React.Dispatch<React.SetStateAction<TabItem[]>>,
  setCurrentFilePath: React.Dispatch<React.SetStateAction<string | null>>,
  setFileCache: React.Dispatch<React.SetStateAction<Record<string, FileCacheItem>>>,
  setOutputHtml: (html: string) => void,
  addTab: (path: string, name: string) => void,
  loadFileContent: (path: string) => Promise<void>,
  chatLoading: boolean
) {
  const [fileTreeData, setFileTreeData] = useState<TreeNode | null>(null);
  const [expandedFolders, setExpandedFolders] = useState<Set<string>>(new Set());
  const [selectedFolder, setSelectedFolder] = useState<string | null>(null);
  const [selectedTreePath, setSelectedTreePath] = useState<string | null>(null);
  const [treeCreateMode, setTreeCreateMode] = useState<'file' | 'folder' | null>(null);
  const [treeCreateParentPath, setTreeCreateParentPath] = useState('');
  const [treeCreateBeforePath, setTreeCreateBeforePath] = useState<string | null>(null);
  const [treeCreateInput, setTreeCreateInput] = useState('');
  const [renameNode, setRenameNode] = useState<{ node: TreeNode; path: string } | null>(null);
  const [renameValue, setRenameValue] = useState('');
  const [copiedFilePath, setCopiedFilePath] = useState<string | null>(null);
  const [copiedNodeType, setCopiedNodeType] = useState<'file' | 'directory' | null>(null);
  const [contextMenu, setContextMenu] = useState<{
    show: boolean;
    x: number;
    y: number;
    node: TreeNode | null;
    showNewFile: boolean;
    showNewFolder: boolean;
    showCopy: boolean;
    showPaste: boolean;
  }>({ show: false, x: 0, y: 0, node: null, showNewFile: false, showNewFolder: false, showCopy: false, showPaste: false });

  const renameSubmittedRef = useRef(false);
  const createSubmittedRef = useRef(false);
  const treeCreateInputRef = useRef<HTMLInputElement>(null);
  const renameInputRef = useRef<HTMLInputElement>(null);
  const initialExpandDoneRef = useRef(false);
  const refreshFolderTimersRef = useRef<Map<string, ReturnType<typeof setTimeout>>>(new Map());

  const loadFileTree = useCallback(async () => {
    const tree = await fsApi.loadTree();
    setFileTreeData(tree);
  }, []);

  const scheduleRefreshFolderList = useCallback((folderPath: string) => {
    const timers = refreshFolderTimersRef.current;
    const existing = timers.get(folderPath);
    if (existing) clearTimeout(existing);
    timers.set(folderPath, setTimeout(async () => {
      timers.delete(folderPath);
      const files = await fsApi.loadList(folderPath);
      if (files) setFileTreeData((prev) => mergeListIntoTree(prev, folderPath, files));
    }, REFRESH_DEBOUNCE_MS));
  }, []);

  useEffect(() => {
    loadFileTree();
  }, [loadFileTree]);

  useEffect(() => {
    if (fileTreeData?.children?.length && !initialExpandDoneRef.current) {
      initialExpandDoneRef.current = true;
      const paths: string[] = [];
      fileTreeData.children.forEach((n) => {
        if (n.type === 'directory' && (n.path || n.name)) paths.push(n.path || n.name);
      });
      if (paths.length) setExpandedFolders((prev) => { const next = new Set(prev); paths.forEach((p) => next.add(p)); return next; });
    }
  }, [fileTreeData]);

  const toggleFolder = useCallback((path: string) => {
    setExpandedFolders((prev) => {
      const next = new Set(prev);
      if (next.has(path)) next.delete(path);
      else next.add(path);
      return next;
    });
  }, []);

  function getParentPathForNew(): string {
    if (selectedFolder) return selectedFolder;
    if (currentFilePath) {
      const parts = currentFilePath.split('/');
      parts.pop();
      return parts.join('/');
    }
    return '';
  }

  const toolbarNewFile = useCallback(() => {
    const parent = getParentPathForNew();
    setTreeCreateParentPath(parent);
    setTreeCreateMode('file');
    setTreeCreateInput('');
    const isFileSelected = selectedTreePath && selectedTreePath !== selectedFolder;
    setTreeCreateBeforePath(isFileSelected ? selectedTreePath : null);
    if (parent) setExpandedFolders((prev) => new Set(prev).add(parent));
    setTimeout(() => treeCreateInputRef.current?.focus(), 50);
  }, [selectedFolder, selectedTreePath, currentFilePath]);

  const toolbarNewFolder = useCallback(() => {
    const parent = getParentPathForNew();
    setTreeCreateParentPath(parent);
    setTreeCreateMode('folder');
    setTreeCreateInput('');
    const isFileSelected = selectedTreePath && selectedTreePath !== selectedFolder;
    setTreeCreateBeforePath(isFileSelected ? selectedTreePath : null);
    if (parent) setExpandedFolders((prev) => new Set(prev).add(parent));
    setTimeout(() => treeCreateInputRef.current?.focus(), 50);
  }, [selectedFolder, selectedTreePath, currentFilePath]);

  const createFileOnServer = useCallback(
    async (path: string) => {
      const parentPath = path.includes('/') ? path.split('/').slice(0, -1).join('/') : '';
      const name = path.split('/').pop() || path;
      setFileTreeData((prev) => insertNodeIntoTree(prev, parentPath, { type: 'file', name, path }));
      try {
        const data = await fsApi.createFile(path, '');
        if (data.success) {
          scheduleRefreshFolderList(parentPath);
          addTab(path, name);
          setOutputHtml(`<span class="output-success">Created: ${path}</span>`);
        } else {
          setFileTreeData((prev) => removeNodeFromTree(prev, path));
          setOutputHtml(`<span class="output-error">${data.detail || 'Failed'}</span>`);
        }
      } catch (e) {
        setFileTreeData((prev) => removeNodeFromTree(prev, path));
        setOutputHtml(`<span class="output-error">${(e as Error).message}</span>`);
      }
    },
    [scheduleRefreshFolderList, addTab, setOutputHtml]
  );

  const createFolderOnServer = useCallback(
    async (path: string) => {
      const parentPath = path.includes('/') ? path.split('/').slice(0, -1).join('/') : '';
      const name = path.split('/').pop() || path;
      setFileTreeData((prev) => insertNodeIntoTree(prev, parentPath, { type: 'directory', name, path, children: [] }));
      try {
        const data = await fsApi.createFolder(path);
        if (data.success) {
          scheduleRefreshFolderList(parentPath);
          setOutputHtml(`<span class="output-success">Folder: ${path}</span>`);
        } else {
          setFileTreeData((prev) => removeNodeFromTree(prev, path));
          setOutputHtml(`<span class="output-error">${data.detail || 'Failed'}</span>`);
        }
      } catch (e) {
        setFileTreeData((prev) => removeNodeFromTree(prev, path));
        setOutputHtml(`<span class="output-error">${(e as Error).message}</span>`);
      }
    },
    [scheduleRefreshFolderList, setOutputHtml]
  );

  const normalizePath = useCallback((p: string) => (p || '').replace(/^\/+|\/+$/g, ''), []);

  const deleteNodeOnServer = useCallback(
    async (path: string) => {
      const pathNorm = normalizePath(path);
      setFileTreeData((prev) => removeNodeFromTree(prev, path));
      try {
        const data = await fsApi.deletePath(path, true);
        if (data.success) {
          setOpenTabs((prev) => {
            const next = prev.filter(
              (t) => normalizePath(t.path) !== pathNorm && !normalizePath(t.path).startsWith(pathNorm + '/')
            );
            setCurrentFilePath((cur) => {
              const curNorm = cur ? normalizePath(cur) : '';
              const currentWasDeleted =
                curNorm === pathNorm || (curNorm.length > 0 && curNorm.startsWith(pathNorm + '/'));
              return currentWasDeleted ? (next.length ? next[next.length - 1].path : null) : cur;
            });
            return next;
          });
          setSelectedFolder((prev) => {
            if (prev == null) return prev;
            const prevNorm = normalizePath(prev);
            return prevNorm === pathNorm || prevNorm.startsWith(pathNorm + '/') ? null : prev;
          });
          setSelectedTreePath((prev) => {
            if (prev == null) return prev;
            const prevNorm = normalizePath(prev);
            return prevNorm === pathNorm || prevNorm.startsWith(pathNorm + '/') ? null : prev;
          });
          setFileCache((prev) => {
            const next = { ...prev };
            for (const p of Object.keys(next)) {
              const pNorm = normalizePath(p);
              if (pNorm === pathNorm || pNorm.startsWith(pathNorm + '/')) delete next[p];
            }
            return next;
          });
          setOutputHtml(`<span class="output-success">Deleted: ${path}</span>`);
        } else {
          await loadFileTree();
          setOutputHtml(`<span class="output-error">${data.detail || 'Failed'}</span>`);
        }
      } catch (e) {
        await loadFileTree();
        setOutputHtml(`<span class="output-error">${(e as Error).message}</span>`);
      }
    },
    [normalizePath, setOpenTabs, setCurrentFilePath, setFileCache, setSelectedFolder, setSelectedTreePath, loadFileTree, setOutputHtml]
  );

  const renameOnServer = useCallback(
    async (oldPath: string, newPath: string) => {
      setFileTreeData((prev) => renameNodeInTree(prev, oldPath, newPath));
      try {
        const data = await fsApi.renamePath(oldPath, newPath);
        if (data.success) {
          setFileCache((prev) => {
            const next = { ...prev };
            if (next[oldPath]) {
              next[newPath] = next[oldPath];
              delete next[oldPath];
            }
            return next;
          });
          setOpenTabs((prev) => prev.map((t) => (t.path === oldPath ? { ...t, path: newPath, name: newPath.split('/').pop() || newPath } : t)));
          if (currentFilePath === oldPath) setCurrentFilePath(newPath);
          setRenameNode(null);
          setOutputHtml(`<span class="output-success">Renamed to ${newPath}</span>`);
        } else {
          await loadFileTree();
          setOutputHtml(`<span class="output-error">${data.detail || 'Failed'}</span>`);
        }
      } catch (e) {
        await loadFileTree();
        setOutputHtml(`<span class="output-error">${(e as Error).message}</span>`);
      }
    },
    [loadFileTree, setFileCache, setOpenTabs, currentFilePath, setCurrentFilePath, setOutputHtml]
  );

  const confirmCreate = useCallback(() => {
    if (chatLoading) return;
    const name = treeCreateInput.trim();
    if (!name) return;
    const path = treeCreateParentPath ? treeCreateParentPath + '/' + name : name;
    if (treeCreateMode === 'file') createFileOnServer(path);
    else createFolderOnServer(path);
    setTreeCreateMode(null);
    setTreeCreateParentPath('');
    setTreeCreateBeforePath(null);
    setTreeCreateInput('');
  }, [chatLoading, treeCreateInput, treeCreateParentPath, treeCreateMode, createFileOnServer, createFolderOnServer]);

  const cancelCreate = useCallback(() => {
    setTreeCreateMode(null);
    setTreeCreateParentPath('');
    setTreeCreateBeforePath(null);
    setTreeCreateInput('');
    createSubmittedRef.current = false;
  }, []);

  const handleRenameKeyDown = useCallback(
    (e: React.KeyboardEvent) => {
      if (e.key === 'Enter' && !chatLoading) {
        e.preventDefault();
        if (!renameNode || renameSubmittedRef.current) return;
        renameSubmittedRef.current = true;
        const oldPath = renameNode.path;
        const name = renameValue.trim();
        if (name && name !== renameNode.node?.name) {
          const newPath = (oldPath.split('/').slice(0, -1).join('/') + '/' + name).replace(/\/+/g, '/');
          renameOnServer(oldPath, newPath);
        } else setRenameNode(null);
      }
      if (e.key === 'Escape') setRenameNode(null);
    },
    [renameNode, renameValue, chatLoading, renameOnServer]
  );

  const handleRenameBlur = useCallback(() => {
    if (!renameNode) return;
    if (renameSubmittedRef.current) {
      renameSubmittedRef.current = false;
      return;
    }
    if (chatLoading) {
      setRenameNode(null);
      return;
    }
    const oldPath = renameNode.path;
    const name = renameValue.trim();
    setRenameNode(null);
    if (!name || name === renameNode.node?.name) return;
    const newPath = (oldPath.split('/').slice(0, -1).join('/') + '/' + name).replace(/\/+/g, '/');
    if (newPath !== oldPath) renameOnServer(oldPath, newPath);
  }, [renameNode, renameValue, chatLoading, renameOnServer]);

  const handleCreateKeyDown = useCallback((e: React.KeyboardEvent) => {
    if (e.key === 'Enter') {
      e.preventDefault();
      if (createSubmittedRef.current) return;
      createSubmittedRef.current = true;
      confirmCreate();
    }
    if (e.key === 'Escape') cancelCreate();
  }, [confirmCreate, cancelCreate]);

  const handleCreateBlur = useCallback(() => {
    if (createSubmittedRef.current) {
      createSubmittedRef.current = false;
      return;
    }
    if (treeCreateInput.trim()) confirmCreate();
    else cancelCreate();
  }, [treeCreateInput, confirmCreate, cancelCreate]);

  function findNodeByPath(nodes: TreeNode[] | undefined, targetPath: string, parentPath: string = ''): TreeNode | null {
    if (!nodes) return null;
    for (const node of nodes) {
      const nodePath = node.path ?? (parentPath ? `${parentPath}/${node.name}` : node.name);
      if (nodePath === targetPath) return node;
      const found = findNodeByPath(node.children, targetPath, nodePath);
      if (found) return found;
    }
    return null;
  }

  const copyDirectoryRecursive = useCallback(
    async (sourceNode: TreeNode, destParentPath: string, destName?: string): Promise<boolean> => {
      const name = destName ?? sourceNode.name;
      const destPath = destParentPath ? `${destParentPath}/${name}` : name;
      if (sourceNode.type === 'directory') {
        const createRes = await fsApi.createFolder(destPath);
        if (!createRes.success) return false;
        for (const child of sourceNode.children ?? []) {
          const childPath = child.path ?? `${sourceNode.path ?? sourceNode.name}/${child.name}`;
          if (child.type === 'file') {
            const contentRes = await fsApi.getFileContent(childPath);
            const content = contentRes.success && contentRes.content != null ? contentRes.content : '';
            const createRes = await fsApi.createFile(`${destPath}/${child.name}`, content);
            if (!createRes.success) return false;
          } else {
            const ok = await copyDirectoryRecursive(child, destPath);
            if (!ok) return false;
          }
        }
        return true;
      }
      const contentRes = await fsApi.getFileContent(sourceNode.path ?? sourceNode.name);
      const content = contentRes.success && contentRes.content != null ? contentRes.content : '';
      const createRes = await fsApi.createFile(destPath, content);
      return createRes.success;
    },
    []
  );

  const handleContextMenuAction = useCallback(
    async (action: 'newFile' | 'newFolder' | 'rename' | 'delete' | 'copy' | 'paste') => {
      const node = contextMenu.node;
      const path = node?.path || node?.name || '';
      const isDir = node?.type === 'directory';
      const parentPath = isDir ? path : (path ? path.split('/').slice(0, -1).join('/') : '');
      setContextMenu((prev) => ({ ...prev, show: false }));
      if (action === 'copy' && path) {
        setCopiedFilePath(path);
        setCopiedNodeType(node?.type === 'directory' ? 'directory' : 'file');
        try {
          await navigator.clipboard.writeText(path);
        } catch {
          // ignore clipboard errors
        }
      } else if (action === 'paste' && copiedFilePath && parentPath !== undefined) {
        if (copiedNodeType === 'file') {
          const base = copiedFilePath.split('/').pop() || 'file';
          const lastDot = base.lastIndexOf('.');
          const name = lastDot > 0 ? base.slice(0, lastDot) : base;
          const ext = lastDot > 0 ? base.slice(lastDot) : '';
          const newName = `${name}_copy${ext}`;
          const newPath = parentPath ? `${parentPath}/${newName}` : newName;
          try {
            const contentRes = await fsApi.getFileContent(copiedFilePath);
            const content = contentRes.success && contentRes.content != null ? contentRes.content : '';
            const createRes = await fsApi.createFile(newPath, content);
            if (createRes.success) {
              setFileTreeData((prev) => insertNodeIntoTree(prev, parentPath, { type: 'file', name: newName, path: newPath }));
              scheduleRefreshFolderList(parentPath);
              addTab(newPath, newName);
              setOutputHtml(`<span class="output-success">Pasted: ${newPath}</span>`);
              if (parentPath) setExpandedFolders((prev) => new Set(prev).add(parentPath));
            } else {
              setOutputHtml(`<span class="output-error">${createRes.detail || 'Paste failed'}</span>`);
            }
          } catch {
            setOutputHtml(`<span class="output-error">Paste failed</span>`);
          }
        } else if (copiedNodeType === 'directory') {
          const sourceNode = findNodeByPath(fileTreeData?.children, copiedFilePath);
          if (!sourceNode) {
            setOutputHtml(`<span class="output-error">Folder not found. Refresh tree and try again.</span>`);
            return;
          }
          const newName = `${sourceNode.name}_copy`;
          const newPath = parentPath ? `${parentPath}/${newName}` : newName;
          try {
            const ok = await copyDirectoryRecursive(sourceNode, parentPath, newName);
            if (!ok) {
              setOutputHtml(`<span class="output-error">Paste folder failed</span>`);
              return;
            }
            setFileTreeData((prev) => insertNodeIntoTree(prev, parentPath, { type: 'directory', name: newName, path: newPath, children: [] }));
            scheduleRefreshFolderList(parentPath);
            setOutputHtml(`<span class="output-success">Pasted folder: ${newPath}</span>`);
            if (parentPath) setExpandedFolders((prev) => new Set(prev).add(parentPath));
          } catch {
            setOutputHtml(`<span class="output-error">Paste folder failed</span>`);
          }
        }
      } else if (action === 'newFile') {
        setTreeCreateParentPath(parentPath);
        setTreeCreateMode('file');
        setTreeCreateInput('');
        setTreeCreateBeforePath(!isDir ? path : null);
        if (parentPath) setExpandedFolders((prev) => new Set(prev).add(parentPath));
        setTimeout(() => treeCreateInputRef.current?.focus(), 50);
      } else if (action === 'newFolder') {
        setTreeCreateParentPath(parentPath);
        setTreeCreateMode('folder');
        setTreeCreateInput('');
        setTreeCreateBeforePath(!isDir ? path : null);
        if (parentPath) setExpandedFolders((prev) => new Set(prev).add(parentPath));
        setTimeout(() => treeCreateInputRef.current?.focus(), 50);
      } else if (action === 'rename' && path) {
        renameSubmittedRef.current = false;
        setRenameNode({ node: node!, path });
        setRenameValue(node?.name || '');
        setTimeout(() => renameInputRef.current?.focus(), 50);
      } else if (action === 'delete' && path) {
        if (confirm(`Delete ${path}?`)) deleteNodeOnServer(path);
      }
    },
    [contextMenu.node, contextMenu.show, copiedFilePath, copiedNodeType, fileTreeData, copyDirectoryRecursive, deleteNodeOnServer, scheduleRefreshFolderList, addTab, setOutputHtml, setExpandedFolders]
  );

  return {
    fileTreeData,
    expandedFolders,
    setExpandedFolders,
    selectedFolder,
    setSelectedFolder,
    selectedTreePath,
    setSelectedTreePath,
    treeCreateMode,
    treeCreateParentPath,
    treeCreateBeforePath,
    treeCreateInput,
    setTreeCreateInput,
    renameNode,
    setRenameNode,
    renameValue,
    setRenameValue,
    contextMenu,
    setContextMenu,
    loadFileTree,
    toggleFolder,
    toolbarNewFile,
    toolbarNewFolder,
    confirmCreate,
    cancelCreate,
    handleRenameKeyDown,
    handleRenameBlur,
    handleCreateKeyDown,
    handleCreateBlur,
    handleContextMenuAction,
    copiedFilePath,
    copiedNodeType,
    createFileOnServer,
    createFolderOnServer,
    deleteNodeOnServer,
    renameOnServer,
    treeCreateInputRef,
    renameInputRef,
    initialExpandDoneRef,
  };
}
