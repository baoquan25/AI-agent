'use client';

import { useState, useEffect, useRef } from 'react';
import type { TreeNode, TabItem, FileCacheItem, ChatMessage } from '../lib/types';
import {
  API_BASE,
  AI_AGENT_URL,
  apiHeaders,
  escapeHtml,
  escapeHtmlAttr,
  stripAnsi,
  formatFileSize,
  getTerminalWsUrl,
} from '../lib/utils';
import { Terminal } from '@xterm/xterm';
import { FitAddon } from '@xterm/addon-fit';
import '@xterm/xterm/css/xterm.css';
export default function Home() {
  const [codeValue, setCodeValue] = useState('');
  const [outputHtml, setOutputHtml] = useState('');
  const [runBusy, setRunBusy] = useState(false);
  const [fileTreeWidth, setFileTreeWidth] = useState(270);
  const [chatSectionWidth, setChatSectionWidth] = useState(320);
  const [resizing, setResizing] = useState<'file' | 'chat' | 'editor' | null>(null);
  const resizeStartRef = useRef({ x: 0, y: 0, width: 0, height: 0 });
  const [editorFlex, setEditorFlex] = useState(65);
  const mainContentRef = useRef<HTMLDivElement>(null);
  const [fileTreeData, setFileTreeData] = useState<TreeNode | null>(null);
  const [expandedFolders, setExpandedFolders] = useState<Set<string>>(new Set());
  const [selectedFolder, setSelectedFolder] = useState<string | null>(null);
  const [selectedTreePath, setSelectedTreePath] = useState<string | null>(null);
  const [currentFilePath, setCurrentFilePath] = useState<string | null>(null);
  const [openTabs, setOpenTabs] = useState<TabItem[]>([]);
  const [fileCache, setFileCache] = useState<Record<string, FileCacheItem>>({});
  const [hasUnsavedChanges, setHasUnsavedChanges] = useState(false);
  const [treeCreateMode, setTreeCreateMode] = useState<'file' | 'folder' | null>(null);
  const [treeCreateParentPath, setTreeCreateParentPath] = useState('');
  const [treeCreateBeforePath, setTreeCreateBeforePath] = useState<string | null>(null);
  const [treeCreateInput, setTreeCreateInput] = useState('');
  const [renameNode, setRenameNode] = useState<{ node: TreeNode; path: string } | null>(null);
  const [renameValue, setRenameValue] = useState('');
  const [contextMenu, setContextMenu] = useState<{
    show: boolean;
    x: number;
    y: number;
    node: TreeNode | null;
    showNewFile: boolean;
    showNewFolder: boolean;
  }>({ show: false, x: 0, y: 0, node: null, showNewFile: false, showNewFolder: false });
  const [sidebarTab, setSidebarTab] = useState<'files' | 'search'>('files');
  const [searchPattern, setSearchPattern] = useState('');
  const [searchResults, setSearchResults] = useState<string[]>([]);
  const [outputTab, setOutputTab] = useState<'output' | 'terminal'>('output');
  const [terminalError, setTerminalError] = useState<string | null>(null);
  const terminalContainerRef = useRef<HTMLDivElement>(null);
  const terminalInstanceRef = useRef<{ term: Terminal; fit: FitAddon; ws: WebSocket } | null>(null);
  const searchInputRef = useRef<HTMLInputElement>(null);
  const [chatMessages, setChatMessages] = useState<ChatMessage[]>([]);
  const [chatLoading, setChatLoading] = useState(false);
  const codeAreaRef = useRef<HTMLTextAreaElement>(null);
  const chatInputRef = useRef<HTMLTextAreaElement>(null);
  const chatAbortRef = useRef<AbortController | null>(null);
  const treeCreateInputRef = useRef<HTMLInputElement>(null);
  const renameInputRef = useRef<HTMLInputElement>(null);
  const contextMenuRef = useRef<HTMLDivElement>(null);
  const initialExpandDoneRef = useRef(false);
  const editorFlexRef = useRef(editorFlex);
  editorFlexRef.current = editorFlex;

  async function loadFileTree() {
    try {
      const res = await fetch(`${API_BASE}/fs/tree`, { headers: apiHeaders() });
      const data = await res.json();
      if (data.success && data.tree) setFileTreeData(data.tree);
    } catch {
      setFileTreeData(null);
    }
  }
  useEffect(() => { loadFileTree(); }, []);

  function addTab(path: string, name: string) {
    setOpenTabs((prev) => (prev.some((t) => t.path === path) ? prev : [...prev, { path, name }]));
    setCurrentFilePath(path);
  }
  function switchTab(path: string) { setCurrentFilePath(path); }
  function closeTab(path: string) {
    const cached = fileCache[path];
    if (cached?.modified && !confirm(`"${path.split('/').pop()}" has unsaved changes. Close anyway?`)) return;
    setOpenTabs((prev) => prev.filter((t) => t.path !== path));
    if (currentFilePath === path) {
      const next = openTabs.filter((t) => t.path !== path);
      setCurrentFilePath(next.length ? next[next.length - 1].path : null);
    }
  }

  async function loadFileContent(path: string) {
    const cached = fileCache[path];
    if (cached) {
      setCodeValue(cached.content);
      setHasUnsavedChanges(cached.modified);
      setOutputHtml(`<span class="output-success">${cached.modified ? '• ' : ''}${path} (from cache)</span>`);
      return;
    }
    try {
      const res = await fetch(`${API_BASE}/fs/file/content?path=${encodeURIComponent(path)}`, { headers: apiHeaders() });
      const data = await res.json();
      if (data.success && data.content != null) {
        setCodeValue(data.content);
        setHasUnsavedChanges(false);
        setFileCache((prev) => ({ ...prev, [path]: { content: data.content, modified: false } }));
        setOutputHtml(`<span class="output-success">Loaded: ${path}</span>`);
      } else {
        setOutputHtml(`<span class="output-error">Failed: ${path}</span>`);
      }
    } catch (e) {
      setOutputHtml(`<span class="output-error"><span class="codicon codicon-error"></span> ${(e as Error).message}</span>`);
    }
  }
  useEffect(() => {
    if (currentFilePath) {
      loadFileContent(currentFilePath);
    } else {
      setCodeValue('');
      setHasUnsavedChanges(false);
    }
  }, [currentFilePath]);

  function handleCodeChange(value: string) {
    setCodeValue(value);
    if (currentFilePath) {
      setFileCache((prev) => ({ ...prev, [currentFilePath]: { content: value, modified: true } }));
      setHasUnsavedChanges(true);
    }
  }

  async function createFileOnServer(path: string) {
    try {
      const res = await fetch(`${API_BASE}/fs/file`, { method: 'POST', headers: apiHeaders(), body: JSON.stringify({ path, content: '' }) });
      const data = await res.json();
      if (data.success) {
        await loadFileTree();
        addTab(path, path.split('/').pop() || path);
        setOutputHtml(`<span class="output-success">Created: ${path}</span>`);
      } else setOutputHtml(`<span class="output-error">${data.detail || 'Failed'}</span>`);
    } catch (e) {
      setOutputHtml(`<span class="output-error">${(e as Error).message}</span>`);
    }
  }
  async function createFolderOnServer(path: string) {
    try {
      const res = await fetch(`${API_BASE}/fs/folder`, { method: 'POST', headers: apiHeaders(), body: JSON.stringify({ path }) });
      const data = await res.json();
      if (data.success) {
        await loadFileTree();
        setOutputHtml(`<span class="output-success">Folder: ${path}</span>`);
      } else setOutputHtml(`<span class="output-error">${data.detail || 'Failed'}</span>`);
    } catch (e) {
      setOutputHtml(`<span class="output-error">${(e as Error).message}</span>`);
    }
  }
  async function deleteNodeOnServer(path: string) {
    try {
      const res = await fetch(`${API_BASE}/fs/path?path=${encodeURIComponent(path)}&recursive=true`, { method: 'DELETE', headers: apiHeaders() });
      const data = await res.json();
      if (data.success) {
        await loadFileTree();
        setOpenTabs((prev) => prev.filter((t) => t.path !== path));
        if (currentFilePath === path) setCurrentFilePath(null);
        setOutputHtml(`<span class="output-success">Deleted: ${path}</span>`);
      } else setOutputHtml(`<span class="output-error">${data.detail || 'Failed'}</span>`);
    } catch (e) {
      setOutputHtml(`<span class="output-error">${(e as Error).message}</span>`);
    }
  }
  async function renameOnServer(oldPath: string, newPath: string) {
    try {
      const res = await fetch(`${API_BASE}/fs/rename`, { method: 'POST', headers: apiHeaders(), body: JSON.stringify({ source: oldPath, destination: newPath }) });
      const data = await res.json();
      if (data.success) {
        await loadFileTree();
        setFileCache((prev) => {
          const next = { ...prev };
          if (next[oldPath]) { next[newPath] = next[oldPath]; delete next[oldPath]; }
          return next;
        });
        setOpenTabs((prev) => prev.map((t) => (t.path === oldPath ? { ...t, path: newPath, name: newPath.split('/').pop() || newPath } : t)));
        if (currentFilePath === oldPath) setCurrentFilePath(newPath);
        setRenameNode(null);
        setOutputHtml(`<span class="output-success">Renamed to ${newPath}</span>`);
      } else setOutputHtml(`<span class="output-error">${data.detail || 'Failed'}</span>`);
    } catch (e) {
      setOutputHtml(`<span class="output-error">${(e as Error).message}</span>`);
    }
  }

  async function saveAllFiles() {
    const modifiedPaths = Object.entries(fileCache).filter(([, v]) => v.modified).map(([k]) => k);
    if (modifiedPaths.length === 0) {
      setOutputHtml(`<span class="output-success">No unsaved changes</span>`);
      return;
    }
    setOutputHtml(`<span style="color:var(--muted)">Saving...</span>`);
    let savedCount = 0;
    const failed: string[] = [];
    for (const path of modifiedPaths) {
      try {
        const res = await fetch(`${API_BASE}/fs/file/content`, { method: 'PUT', headers: apiHeaders(), body: JSON.stringify({ path, content: fileCache[path].content }) });
        const data = await res.json();
        if (data.success) {
          setFileCache((prev) => ({ ...prev, [path]: { ...prev[path], modified: false } }));
          savedCount++;
        } else failed.push(path);
      } catch { failed.push(path); }
    }
    if (failed.length === 0) setOutputHtml(`<span class="output-success">Saved ${savedCount} file(s)</span>`);
    else setOutputHtml(`<span class="output-error">Saved ${savedCount}/${modifiedPaths.length}. Failed: ${failed.join(', ')}</span>`);
    setHasUnsavedChanges(false);
  }

  async function runCode() {
    setRunBusy(true);
    setOutputHtml(`<span style="color:var(--muted)">Running...</span>`);
    try {
      const payload = {
        code: codeValue,
        use_jupyter: true,
        file_path: currentFilePath || undefined,
      };
      const res = await fetch(`${API_BASE}/run`, { method: 'POST', headers: apiHeaders(), body: JSON.stringify(payload) });
      const data = await res.json();
      if (!res.ok) {
        setOutputHtml(`<span class="output-error">${data.detail || 'Failed'}</span>`);
        setRunBusy(false);
        return;
      }
      let html = '';
      const isError = data.success === false;
      const textOut = data.output ?? data.stdout ?? '';
      if (textOut) {
        const pre = `<pre class="output-stdout">${escapeHtml(stripAnsi(textOut))}</pre>`;
        html += isError ? `<div class="output-error">${pre}</div>` : pre;
      }
      const richList = data.outputs ?? data.rich_output ?? [];
      if (Array.isArray(richList) && richList.length > 0) {
        richList.forEach((item: { type?: string; data?: string; library?: string; lib?: string }, i: number) => {
          const type = item.type || '';
          const d = item.data || '';
          const lib = item.library ?? item.lib ?? '';
          if (type.startsWith('image/')) html += `<div class="rich-output-item"><div class="rich-output-label"><span class="codicon codicon-graph"></span> ${lib || 'Chart'} ${i + 1}</div><img src="data:${type};base64,${d}" alt="Output" /></div>`;
          else if (type === 'text/html') html += `<div class="rich-output-item"><div class="rich-output-label"><span class="codicon codicon-graph-line"></span> ${lib || 'HTML'} ${i + 1}</div><div class="rich-output-html">${d}</div></div>`;
          else if (type === 'image/svg+xml') html += `<div class="rich-output-item"><div class="rich-output-label"><span class="codicon codicon-paintcan"></span> SVG ${i + 1}</div><div style="background:white;padding:10px;">${d}</div></div>`;
        });
      }
      if (!html) html = isError ? `<span class="output-error">Execution failed</span>` : `<span class="output-success">Done</span>`;
      setOutputHtml(html);
    } catch (e) {
      setOutputHtml(`<span class="output-error">${(e as Error).message}</span>`);
    }
    setRunBusy(false);
  }

  function toggleFolder(path: string) {
    setExpandedFolders((prev) => {
      const next = new Set(prev);
      if (next.has(path)) next.delete(path);
      else next.add(path);
      return next;
    });
  }
  function getParentPathForNew(): string {
    if (selectedFolder) return selectedFolder;
    if (currentFilePath) { const parts = currentFilePath.split('/'); parts.pop(); return parts.join('/'); }
    return '';
  }
  function toolbarNewFile() {
    const parent = getParentPathForNew();
    setTreeCreateParentPath(parent);
    setTreeCreateMode('file');
    setTreeCreateInput('');
    const isFileSelected = selectedTreePath && selectedTreePath !== selectedFolder;
    setTreeCreateBeforePath(isFileSelected ? selectedTreePath : null);
    if (parent) setExpandedFolders((prev) => new Set(prev).add(parent));
    setTimeout(() => treeCreateInputRef.current?.focus(), 50);
  }
  function toolbarNewFolder() {
    const parent = getParentPathForNew();
    setTreeCreateParentPath(parent);
    setTreeCreateMode('folder');
    setTreeCreateInput('');
    const isFileSelected = selectedTreePath && selectedTreePath !== selectedFolder;
    setTreeCreateBeforePath(isFileSelected ? selectedTreePath : null);
    if (parent) setExpandedFolders((prev) => new Set(prev).add(parent));
    setTimeout(() => treeCreateInputRef.current?.focus(), 50);
  }
  function confirmCreate() {
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
  }
  function cancelCreate() {
    setTreeCreateMode(null);
    setTreeCreateParentPath('');
    setTreeCreateBeforePath(null);
    setTreeCreateInput('');
  }
  function handleRenameBlur() {
    if (!renameNode) return;
    if (chatLoading) { setRenameNode(null); return; }
    const oldPath = renameNode.path;
    const oldName = renameNode.node?.name ?? '';
    const name = renameValue.trim();
    setRenameNode(null);
    if (!name || name === oldName) return;
    const newPath = (oldPath.split('/').slice(0, -1).join('/') + '/' + name).replace(/\/+/g, '/');
    if (newPath !== oldPath) renameOnServer(oldPath, newPath);
  }
  function handleCreateBlur() {
    if (treeCreateInput.trim()) confirmCreate();
    else cancelCreate();
  }
  function handleContextMenuAction(action: 'newFile' | 'newFolder' | 'rename' | 'delete') {
    const node = contextMenu.node;
    const path = node?.path || node?.name || '';
    const isDir = node?.type === 'directory';
    const parentPath = isDir ? path : (path ? path.split('/').slice(0, -1).join('/') : '');
    setContextMenu((prev) => ({ ...prev, show: false }));
    if (action === 'newFile') {
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
      setRenameNode({ node: node!, path });
      setRenameValue(node?.name || '');
      setTimeout(() => renameInputRef.current?.focus(), 50);
    } else if (action === 'delete' && path) {
      if (confirm(`Delete ${path}?`)) deleteNodeOnServer(path);
    }
  }
  function openSearchTab() { setSidebarTab('search'); setSearchResults([]); setTimeout(() => searchInputRef.current?.focus(), 50); }
  async function searchFiles(patternOverride?: string) {
    const pattern = (patternOverride ?? searchPattern).trim();
    if (!pattern) { setSearchResults([]); return; }
    try {
      const res = await fetch(`${API_BASE}/fs/search`, { method: 'POST', headers: apiHeaders(), body: JSON.stringify({ pattern, path: '' }) });
      const data = await res.json();
      setSearchResults(data.success && data.matches?.length ? data.matches : []);
    } catch (e) {
      setSearchResults([`Error: ${(e as Error).message}`]);
    }
  }
  async function sendChat() {
    const ta = chatInputRef.current;
    if (!ta) return;
    const text = ta.value.trim();
    if (!text || chatLoading) return;
    setChatMessages((prev) => [...prev, { sender: 'user', text }, { sender: 'ai', text: 'Thinking...', isThinking: true }]);
    ta.value = '';
    setChatLoading(true);
    chatAbortRef.current = new AbortController();
    try {
      const res = await fetch(AI_AGENT_URL, {
        method: 'POST',
        headers: apiHeaders(),
        body: JSON.stringify({ message: text }),
        signal: chatAbortRef.current.signal,
      });
      const data = await res.json();
      const codeOutputs = data.code_outputs ?? data.results ?? [];
      if (Array.isArray(codeOutputs) && codeOutputs.length > 0) {
        let html = '';
        let firstCreatedPath: string | null = null;
        for (let i = 0; i < codeOutputs.length; i++) {
          const item = codeOutputs[i] as { success?: boolean; file_path?: string; output?: string; exit_code?: number; outputs?: Array<{ type?: string; data?: string; library?: string }> };
          const label = item.file_path ? `Agent ran: ${item.file_path}` : 'Agent executed code';
          const iconCls = item.success ? 'codicon codicon-check' : 'codicon codicon-error';
          const cls = item.success ? 'output-success' : 'output-error';
          if (i > 0) html += '<hr class="output-divider" style="border:none;border-top:2px dashed #aaa;margin:10px 0;">';
          html += `<div style="margin-bottom:4px;"><span class="${cls}">${escapeHtml(label)} (exit: ${item.exit_code ?? ''})</span></div>`;
          if (item.output) html += `<pre class="output-stdout">${escapeHtml(stripAnsi(item.output))}</pre>`;
          const richList = item.outputs ?? [];
          if (Array.isArray(richList) && richList.length > 0) {
            richList.forEach((r: { type?: string; data?: string; library?: string }, ri: number) => {
              const type = r.type || '';
              const d = r.data || '';
              const lib = r.library || '';
              if (type.startsWith('image/')) html += `<div class="rich-output-item"><div class="rich-output-label"><span class="codicon codicon-graph"></span> ${lib || 'Chart'} ${ri + 1}</div><img src="data:${type};base64,${d}" alt="Output" /></div>`;
              else if (type === 'text/html') html += `<div class="rich-output-item"><div class="rich-output-label"><span class="codicon codicon-graph-line"></span> ${lib || 'HTML'} ${ri + 1}</div><div class="rich-output-html">${d}</div></div>`;
              else if (type === 'image/svg+xml') html += `<div class="rich-output-item"><div class="rich-output-label"><span class="codicon codicon-paintcan"></span> SVG ${ri + 1}</div><div style="background:white;padding:10px;">${d}</div></div>`;
            });
          }
          if (item.success && item.file_path && !firstCreatedPath) firstCreatedPath = item.file_path;
        }
        setOutputHtml(html || '<span class="output-success">Done</span>');
        if (firstCreatedPath) {
          addTab(firstCreatedPath, firstCreatedPath.split('/').pop() || firstCreatedPath);
          loadFileContent(firstCreatedPath);
        }
      }
      const reply = data.agent_reply ?? data.reply ?? data.message ?? (data.error ? String(data.error) : 'No response');
      setChatMessages((prev) => prev.filter((m) => !m.isThinking).concat([{ sender: 'ai', text: reply, icon: data.error ? 'error' : 'success' }]));
      await loadFileTree();
    } catch (e) {
      setChatMessages((prev) => prev.filter((m) => !m.isThinking).concat([{ sender: 'ai', text: (e as Error).message, icon: 'error' }]));
    }
    setChatLoading(false);
    chatAbortRef.current = null;
  }
  function openTerminalTab() {
    setTerminalError(null);
    setOutputTab('terminal');
  }

  useEffect(() => {
    if (outputTab !== 'terminal' || !terminalContainerRef.current) return;
    const container = terminalContainerRef.current;
    const term = new Terminal({
      cursorBlink: true,
      theme: { background: '#000000', foreground: '#ccc' },
      fontSize: 13,
      fontFamily: 'Menlo, Monaco, "Courier New", monospace',
    });
    const fit = new FitAddon();
    term.loadAddon(fit);
    term.open(container);
    fit.fit();

    const wsUrl = getTerminalWsUrl();
    const ws = new WebSocket(wsUrl);
    ws.binaryType = 'arraybuffer';

    ws.onopen = () => {
      setTerminalError(null);
      requestAnimationFrame(() => {
        fit.fit();
        if (ws.readyState === WebSocket.OPEN) {
          ws.send(JSON.stringify({ type: 'resize', cols: term.cols, rows: term.rows }));
        }
      });
    };
    ws.onmessage = (ev) => {
      if (ev.data instanceof ArrayBuffer) {
        const str = new TextDecoder().decode(ev.data);
        term.write(str);
      } else if (typeof ev.data === 'string') {
        term.write(ev.data);
      }
    };
    ws.onerror = () => setTerminalError('WebSocket error');
    ws.onclose = () => setTerminalError('Terminal disconnected');

    term.onData((data) => {
      if (ws.readyState === WebSocket.OPEN) {
        ws.send(new TextEncoder().encode(data));
      }
    });

    const resizeObserver = new ResizeObserver(() => {
      fit.fit();
      if (ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify({ type: 'resize', cols: term.cols, rows: term.rows }));
      }
    });
    resizeObserver.observe(container);

    terminalInstanceRef.current = { term, fit, ws };

    return () => {
      resizeObserver.disconnect();
      ws.close();
      term.dispose();
      terminalInstanceRef.current = null;
    };
  }, [outputTab]);

  function startResizeFile(e: React.MouseEvent) {
    e.preventDefault();
    resizeStartRef.current = { x: e.clientX, y: 0, width: fileTreeWidth, height: 0 };
    setResizing('file');
  }
  function startResizeChat(e: React.MouseEvent) {
    e.preventDefault();
    resizeStartRef.current = { x: e.clientX, y: 0, width: chatSectionWidth, height: 0 };
    setResizing('chat');
  }
  function startResizeEditor(e: React.MouseEvent) {
    e.preventDefault();
    const mainEl = mainContentRef.current;
    if (!mainEl) return;
    resizeStartRef.current = { x: 0, y: e.clientY, width: editorFlexRef.current, height: mainEl.getBoundingClientRect().height };
    setResizing('editor');
  }

  useEffect(() => {
    if (!resizing) return;
    const onMove = (e: MouseEvent) => {
      if (resizing === 'file') {
        const delta = e.clientX - resizeStartRef.current.x;
        setFileTreeWidth(Math.max(80, Math.min(500, resizeStartRef.current.width + delta)));
      } else if (resizing === 'chat') {
        const delta = e.clientX - resizeStartRef.current.x;
        setChatSectionWidth(Math.max(200, resizeStartRef.current.width - delta));
      } else if (resizing === 'editor') {
        const totalH = resizeStartRef.current.height;
        if (totalH <= 0) return;
        const deltaY = e.clientY - resizeStartRef.current.y;
        const deltaPct = (deltaY / totalH) * 100;
        setEditorFlex(Math.max(15, Math.min(85, resizeStartRef.current.width + deltaPct)));
      }
    };
    const onUp = () => setResizing(null);
    document.body.style.cursor = resizing === 'editor' ? 'row-resize' : 'col-resize';
    document.body.style.userSelect = 'none';
    document.addEventListener('mousemove', onMove);
    document.addEventListener('mouseup', onUp);
    return () => {
      document.removeEventListener('mousemove', onMove);
      document.removeEventListener('mouseup', onUp);
      document.body.style.cursor = '';
      document.body.style.userSelect = '';
    };
  }, [resizing]);

  useEffect(() => {
    const onKeyDown = (e: KeyboardEvent) => {
      if (e.ctrlKey && e.key === 's') { e.preventDefault(); if (!chatLoading) saveAllFiles(); }
      if (e.ctrlKey && e.key === 'p') { e.preventDefault(); if (!chatLoading) openSearchTab(); }
      if (e.ctrlKey && e.key === 'w' && currentFilePath) { e.preventDefault(); closeTab(currentFilePath); }
      if (e.key === 'Escape') {
        if (treeCreateMode) cancelCreate();
        setContextMenu((prev) => ({ ...prev, show: false }));
        setRenameNode(null);
      }
    };
    window.addEventListener('keydown', onKeyDown);
    return () => window.removeEventListener('keydown', onKeyDown);
  }, [currentFilePath, treeCreateMode, chatLoading]);

  useEffect(() => {
    const onBeforeUnload = (e: BeforeUnloadEvent) => {
      const hasModified = Object.values(fileCache).some((v) => v.modified);
      if (hasModified) e.preventDefault();
    };
    window.addEventListener('beforeunload', onBeforeUnload);
    return () => window.removeEventListener('beforeunload', onBeforeUnload);
  }, [fileCache]);

  useEffect(() => {
    if (!contextMenu.show) return;
    function onPointerDown(e: MouseEvent) {
      const el = contextMenuRef.current;
      if (el && !el.contains(e.target as Node)) setContextMenu((prev) => ({ ...prev, show: false }));
    }
    document.addEventListener('mousedown', onPointerDown);
    return () => document.removeEventListener('mousedown', onPointerDown);
  }, [contextMenu.show]);

  useEffect(() => {
    if (fileTreeData?.children?.length && !initialExpandDoneRef.current) {
      initialExpandDoneRef.current = true;
      const paths: string[] = [];
      fileTreeData.children.forEach((n) => { if (n.type === 'directory' && (n.path || n.name)) paths.push(n.path || n.name); });
      if (paths.length) setExpandedFolders((prev) => { const next = new Set(prev); paths.forEach((p) => next.add(p)); return next; });
    }
  }, [fileTreeData]);

  useEffect(() => {
    if (sidebarTab !== 'search') return;
    if (!searchPattern.trim()) { setSearchResults([]); return; }
    const t = setTimeout(() => searchFiles(), 300);
    return () => clearTimeout(t);
  }, [sidebarTab, searchPattern]);

  function renderTreeNode(node: TreeNode, level: number, firstLevel: boolean): React.ReactNode {
    const path = node.path || node.name;
    const isDir = node.type === 'directory';
    const hasChildren = isDir && node.children && node.children.length > 0;
    const shouldExpand = isDir && (expandedFolders.has(path) || (firstLevel && !initialExpandDoneRef.current));
    const isPy = node.type === 'file' && node.name.toLowerCase().endsWith('.py');
    const isSelected = path === selectedTreePath;
    const leadIcon = isDir
      ? (shouldExpand ? <span className={"tree-lead-icon codicon codicon-chevron-down"} onClick={(e) => { e.stopPropagation(); toggleFolder(path); }} title="Thu gọn" /> : <span className={"tree-lead-icon codicon codicon-chevron-right"} onClick={(e) => { e.stopPropagation(); toggleFolder(path); }} title="Mở rộng" />)
      : isPy ? <span className={"tree-lead-icon codicon codicon-python"} /> : <span className={"tree-lead-icon codicon codicon-file"} />;
    const paddingLeft = 8 + level * 8;

    if (renameNode?.path === path) {
      return (
        <div key={path} className="tree-item" style={{ paddingLeft }}>
          <div className="tree-item-content">
            {leadIcon}
            <input ref={renameInputRef} type="text" className="tree-inline-input" value={renameValue} onChange={(e) => setRenameValue(e.target.value)}
              onBlur={handleRenameBlur}
              onKeyDown={(e) => {
                if (e.key === 'Enter' && !chatLoading) renameOnServer(path, (path.split('/').slice(0, -1).join('/') + '/' + renameValue.trim()).replace(/\/+/g, '/'));
                if (e.key === 'Escape') setRenameNode(null);
              }}
            />
          </div>
        </div>
      );
    }

    return (
      <div key={path}>
        <div className={`tree-item ${isSelected ? 'selected' : ''}`} style={{ paddingLeft }}
          onClick={() => {
            setSelectedTreePath(path);
            if (isDir) setSelectedFolder(path);
            else setSelectedFolder(path ? path.split('/').slice(0, -1).join('/') : '');
            if (chatLoading) {
              if (!isDir && openTabs.some((t) => t.path === path)) switchTab(path);
            } else {
              if (!isDir) { addTab(path, node.name); loadFileContent(path); }
            }
          }}
          onContextMenu={(e) => { if (chatLoading) return; e.preventDefault(); setContextMenu({ show: true, x: e.clientX, y: e.clientY, node, showNewFile: true, showNewFolder: true }); }}
        >
          <div className="tree-item-content">
            {leadIcon}
            <span className="tree-item-name">{node.name}</span>
            {node.size != null && <span className="tree-item-size">{formatFileSize(node.size)}</span>}
          </div>
        </div>
        {(hasChildren || (path === treeCreateParentPath && treeCreateMode) || (isDir && shouldExpand)) && (
          <div className="tree-children" style={{ display: shouldExpand ? 'block' : 'none' }}>
            {path === treeCreateParentPath && treeCreateMode && !treeCreateBeforePath && (
              <div className="tree-item tree-inline-create-row" style={{ paddingLeft: 8 + (level + 1) * 8 }}>
                <div className="tree-item-content">
                  <span className={`tree-lead-icon codicon codicon-${treeCreateMode === 'file' ? 'list-flat' : 'chevron-right'}`} style={{ pointerEvents: 'none' }} />
                  <input ref={treeCreateInputRef} type="text" className="tree-inline-input" placeholder={treeCreateMode === 'file' ? 'File name' : 'Folder name'} value={treeCreateInput} onChange={(e) => setTreeCreateInput(e.target.value)}
                    onBlur={handleCreateBlur}
                    onKeyDown={(e) => { if (e.key === 'Enter') confirmCreate(); if (e.key === 'Escape') cancelCreate(); }}
                  />
                </div>
              </div>
            )}
            {node.children?.map((child) => {
              const childPath = child.path || child.name;
              const showCreateBefore = path === treeCreateParentPath && treeCreateMode && treeCreateBeforePath === childPath;
              return (
                <div key={childPath}>
                  {showCreateBefore && (
                    <div className="tree-item tree-inline-create-row" style={{ paddingLeft: 8 + (level + 1) * 8 }}>
                      <div className="tree-item-content">
                        <span className={`tree-lead-icon codicon codicon-${treeCreateMode === 'file' ? 'list-flat' : 'chevron-right'}`} style={{ pointerEvents: 'none' }} />
                        <input ref={treeCreateInputRef} type="text" className="tree-inline-input" placeholder={treeCreateMode === 'file' ? 'File name' : 'Folder name'} value={treeCreateInput} onChange={(e) => setTreeCreateInput(e.target.value)}
                          onBlur={handleCreateBlur}
                          onKeyDown={(e) => { if (e.key === 'Enter') confirmCreate(); if (e.key === 'Escape') cancelCreate(); }}
                        />
                      </div>
                    </div>
                  )}
                  {renderTreeNode(child, level + 1, false)}
                </div>
              );
            })}
          </div>
        )}
      </div>
    );
  }

  const treeContent = !fileTreeData || !fileTreeData.children?.length
    ? <div className="tree-empty">{fileTreeData === null ? 'Failed to load' : 'No files yet'}</div>
    : fileTreeData.children.map((node) => {
        const nodePath = node.path || node.name;
        const showCreateBefore = treeCreateMode && treeCreateParentPath === '' && treeCreateBeforePath === nodePath;
        return (
          <div key={nodePath}>
            {showCreateBefore && (
              <div className="tree-item tree-inline-create-row" style={{ paddingLeft: 8 }}>
                <div className="tree-item-content">
                  <span className={`tree-lead-icon codicon codicon-${treeCreateMode === 'file' ? 'list-flat' : 'chevron-right'}`} style={{ pointerEvents: 'none' }} />
                  <input ref={treeCreateInputRef} type="text" className="tree-inline-input" placeholder={treeCreateMode === 'file' ? 'File name' : 'Folder name'} value={treeCreateInput} onChange={(e) => setTreeCreateInput(e.target.value)} onBlur={handleCreateBlur} onKeyDown={(e) => { if (e.key === 'Enter') confirmCreate(); if (e.key === 'Escape') cancelCreate(); }} />
                </div>
              </div>
            )}
            {renderTreeNode(node, 0, true)}
          </div>
        );
      });

  const modifiedCount = Object.values(fileCache).filter((v) => v.modified).length;

  return (
    <>
      <header>
        <span className="brand">Agent</span>
      </header>
      <div className="container">
        <div style={{ width: fileTreeWidth, minWidth: 80, flexShrink: 0, display: 'flex', flexDirection: 'column' }}>
          <div className="section" id="fileTreeSection">
            <div className="sidebar-toolbar">
              <button type="button" className={`sidebar-tab ${sidebarTab === 'files' ? 'active' : ''}`} onClick={() => setSidebarTab('files')} title="Files"><span className="codicon codicon-files" /></button>
              <button type="button" className={`sidebar-tab ${sidebarTab === 'search' ? 'active' : ''}`} onClick={() => { setSidebarTab('search'); setTimeout(() => searchInputRef.current?.focus(), 50); }} title="Search (Ctrl+P)"><span className="codicon codicon-search" /></button>
            </div>
            {sidebarTab === 'files' && (
              <div className="file-tree-section">
                <div className="file-tree-header">
                  <span className="file-tree-title">WORKSPACE</span>
                  <div className="file-tree-actions">
                    <button type="button" className="icon-btn" onClick={toolbarNewFile} title="New File" disabled={chatLoading}><span className="codicon codicon-new-file" /></button>
                    <button type="button" className="icon-btn" onClick={toolbarNewFolder} title="New Folder" disabled={chatLoading}><span className="codicon codicon-new-folder" /></button>
                    <button type="button" className="icon-btn" onClick={loadFileTree} title="Refresh" disabled={chatLoading}><span className="codicon codicon-refresh" /></button>
                    <button type="button" className="icon-btn" onClick={saveAllFiles} disabled={chatLoading} title={modifiedCount > 0 ? `Save All (${modifiedCount} unsaved)` : 'Save All (Ctrl+S)'}><span className="codicon codicon-save-all" /></button>
                  </div>
                </div>
                <div id="fileTree">
                  {treeCreateMode && treeCreateParentPath === '' && !treeCreateBeforePath && (
                    <div className="tree-item tree-inline-create-row" style={{ paddingLeft: 8 }}>
                      <div className="tree-item-content">
                        <span className={`tree-lead-icon codicon codicon-${treeCreateMode === 'file' ? 'list-flat' : 'chevron-right'}`} style={{ pointerEvents: 'none' }} />
                        <input ref={treeCreateInputRef} type="text" className="tree-inline-input" placeholder={treeCreateMode === 'file' ? 'File name' : 'Folder name'} value={treeCreateInput} onChange={(e) => setTreeCreateInput(e.target.value)} onBlur={handleCreateBlur} onKeyDown={(e) => { if (e.key === 'Enter') confirmCreate(); if (e.key === 'Escape') cancelCreate(); }} />
                      </div>
                    </div>
                  )}
                  {treeContent}
                </div>
              </div>
            )}
            {sidebarTab === 'search' && (
              <div className="sidebar-search-panel">
                <div className="sidebar-search-header">Search</div>
                <div className="sidebar-search-row">
                  <input ref={searchInputRef} type="text" className="sidebar-search-input" value={searchPattern} onChange={(e) => setSearchPattern(e.target.value)} placeholder="Search" />
                </div>
                <div className="sidebar-search-results">
                  {searchResults.length === 0 ? <div className="sidebar-search-empty">No files found</div> : searchResults.map((match) => (
                    <div key={match} className="sidebar-search-item" onClick={() => {
                      if (chatLoading) { if (openTabs.some((t) => t.path === match)) switchTab(match); return; }
                      loadFileContent(match);
                      addTab(match, match.split('/').pop() || match);
                    }}>
                      <span className={`codicon ${match.toLowerCase().endsWith('.py') ? 'codicon-python' : 'codicon-file'}`} style={{ marginRight: 6, fontSize: 12 }} />{match}
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        </div>
        <div className={`resizer-v ${resizing === 'file' ? 'resizing' : ''}`} onMouseDown={startResizeFile} title="Kéo để đổi độ rộng" />
        <div className="main-content" ref={mainContentRef}>
          <div className="section" id="editorSection" style={{ flex: `${editorFlex} 0 0` }}>
            {openTabs.length > 0 ? (
              <>
                <div className="editor-tabs-bar">
                  <div className="editor-tabs">
                    {openTabs.map((tab) => {
                      const cached = fileCache[tab.path];
                      const isModified = cached?.modified;
                      const isPy = tab.name.toLowerCase().endsWith('.py');
                      const fileIcon = isPy ? 'codicon-python' : 'codicon-file';
                      return (
                        <div key={tab.path} className={`editor-tab ${tab.path === currentFilePath ? 'active' : ''}`} title={tab.path} onClick={() => switchTab(tab.path)} onAuxClick={(e) => { if (e.button === 1) { e.preventDefault(); closeTab(tab.path); } }}>
                          <span className={`codicon ${fileIcon}`} style={{ fontSize: 12, flexShrink: 0 }} />
                          <span className="tab-name">{isModified && <span className="codicon codicon-close-dirty" style={{ marginRight: 4 }} />}{tab.name}</span>
                          <span className="tab-close" onClick={(e) => { e.stopPropagation(); closeTab(tab.path); }}><span className="codicon codicon-close" /></span>
                        </div>
                      );
                    })}
                  </div>
                  <div className="actions">
                    <button type="button" className="btn-run" onClick={runCode} disabled={runBusy || chatLoading} title={runBusy ? 'Running...' : 'Run'}><div className="spinner" style={{ display: runBusy ? 'inline-block' : 'none' }} /><span className="codicon codicon-play" /></button>
                  </div>
                </div>
                <textarea ref={codeAreaRef} id="codeArea" spellCheck={false} value={codeValue} readOnly={chatLoading} onChange={(e) => handleCodeChange(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === 'Tab') { e.preventDefault(); const ta = codeAreaRef.current; if (!ta) return; const start = ta.selectionStart, end = ta.selectionEnd; const newVal = ta.value.slice(0, start) + '    ' + ta.value.slice(end); handleCodeChange(newVal); setTimeout(() => { ta.selectionStart = ta.selectionEnd = start + 4; }, 0); }
                    if (e.ctrlKey && e.key === 'Enter' && !chatLoading) runCode();
                  }}
                />
              </>
            ) : null}
          </div>
          <div className={`resizer-h ${resizing === 'editor' ? 'resizing' : ''}`} onMouseDown={startResizeEditor} title="Kéo để đổi chiều cao" />
          <div className="section" id="outputSection" style={{ flex: `${100 - editorFlex} 0 0`, display: 'flex', flexDirection: 'column' }}>
            <div className="output-tabs-bar">
              <button
                type="button"
                className={`output-tab ${outputTab === 'output' ? 'active' : ''}`}
                onClick={() => setOutputTab('output')}
              >
                Output
              </button>
              <button
                type="button"
                className={`output-tab ${outputTab === 'terminal' ? 'active' : ''}`}
                onClick={openTerminalTab}
              >
                Terminal
              </button>
            </div>
            <div className={`panel-scroll output-panel ${outputTab === 'output' ? '' : 'hidden'}`}>
              <div id="output" dangerouslySetInnerHTML={{ __html: outputHtml }} />
            </div>
            {outputTab === 'terminal' && (
              <div className="panel-scroll terminal-panel">
                {terminalError && (
                  <div className="terminal-status" style={{ padding: 8, color: 'var(--error)', fontSize: 12 }}>{terminalError}</div>
                )}
                <div ref={terminalContainerRef} className="xterm-container" style={{ width: '100%', height: '100%', minHeight: 120 }} />
              </div>
            )}
          </div>
        </div>
        <div className={`resizer-v ${resizing === 'chat' ? 'resizing' : ''}`} onMouseDown={startResizeChat} title="Kéo để đổi độ rộng" />
        <div className="section" id="chatSection" style={{ width: chatSectionWidth, minWidth: 200, flex: 'none', display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
          <div id="chatMessages">
            {chatMessages.map((msg, i) => (
              <div key={i} className={`chat-bubble ${msg.sender} ${msg.isThinking ? 'thinking' : ''}`}>{msg.text}{msg.icon === 'error' && <span className="codicon codicon-error" style={{ marginLeft: 6 }} />}</div>
            ))}
          </div>
          <div className="chat-input-area">
            <textarea ref={chatInputRef} id="chatInput" placeholder="Ask AI..." rows={2} disabled={chatLoading} onKeyDown={(e) => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); sendChat(); } }} />
          </div>
        </div>
      </div>
      <div ref={contextMenuRef} className="context-menu" style={{ display: contextMenu.show ? 'block' : 'none', left: contextMenu.x, top: contextMenu.y }}>
        {contextMenu.showNewFile && <div className="context-menu-item" onClick={() => handleContextMenuAction('newFile')}>New File...</div>}
        {contextMenu.showNewFolder && <div className="context-menu-item" onClick={() => handleContextMenuAction('newFolder')}>New Folder...</div>}
        <div className="context-menu-item" onClick={() => handleContextMenuAction('rename')}>Rename...</div>
        <div className="context-menu-item" onClick={() => handleContextMenuAction('delete')}>Delete permanently</div>
      </div>

    </>
  );
}
