'use client';

import { useRef, useEffect, useCallback, useMemo, useState } from 'react';
import { Header } from '../components/layout/Header';
import { Footer } from '../components/layout/Footer';
import { Resizer } from '../components/layout/Resizer';
import { FileTreeSidebar } from '../components/leftbar/FileTreeSidebar';
import { ContextMenu } from '../components/leftbar/ContextMenu';
import { EditorSection } from '../components/editor/EditorSection';
import { OutputSection } from '../components/output/OutputSection';
import { RightBar } from '../components/rightbar/RightBar';
import { useFileTabs } from '../hooks/useFileTabs';
import { useRunCode } from '../hooks/useRunCode';
import { useFileContent } from '../hooks/useFileContent';
import { useSearch } from '../hooks/useSearch';
import { useTerminal } from '../hooks/useTerminal';
import { useChat } from '../hooks/useChat';
import { useFileTree } from '../hooks/useFileTree';
import { useResize } from '../hooks/useResize';
import { useKeyboardShortcuts } from '../hooks/useKeyboardShortcuts';
import { useFileWatch } from '../hooks/useFileWatch';
import type { FileChangeEvent } from '../hooks/useFileWatch';
import { useDiffReview } from '../hooks/useDiffReview';

export default function Home() {
  const loadFileTreeRef = useRef<() => Promise<void>>(() => Promise.resolve());
  const contextMenuRef = useRef<HTMLDivElement>(null);

  const fileTabs = useFileTabs();
  const runCode = useRunCode();
  const fileContent = useFileContent(
    fileTabs.currentFilePath,
    fileTabs.fileCache,
    fileTabs.setFileCache,
    runCode.setOutputHtml
  );
  const search = useSearch();
  const terminal = useTerminal();
  const diffReview = useDiffReview(
    fileContent.setFileContentDirect,
    fileTabs.currentFilePath,
    fileTabs.addTab,
  );
  const chat = useChat(runCode.setOutputHtml, terminal.setOutputTab, () => loadFileTreeRef.current(), diffReview.addDiffs);

  const fileTree = useFileTree(
    fileTabs.openTabs,
    fileTabs.currentFilePath,
    fileTabs.setOpenTabs,
    fileTabs.setCurrentFilePath,
    fileTabs.setFileCache,
    runCode.setOutputHtml,
    fileTabs.addTab,
    fileContent.loadFileContent,
    chat.chatLoading
  );

  useEffect(() => {
    loadFileTreeRef.current = fileTree.loadFileTree;
  }, [fileTree.loadFileTree]);

  // ── Real-time file watch (VS Code–style event-driven updates) ───────────
  const currentFilePathRef = useRef(fileTabs.currentFilePath);
  currentFilePathRef.current = fileTabs.currentFilePath;
  const fileCacheRef = useRef(fileTabs.fileCache);
  fileCacheRef.current = fileTabs.fileCache;

  const handleFileChanges = useCallback((changes: FileChangeEvent[]) => {
    for (const change of changes) {
      const norm = (p: string) => (p || '').replace(/^\/+|\/+$/g, '');
      const path = norm(change.path);
      const parentPath = path.includes('/') ? path.split('/').slice(0, -1).join('/') : '';

      switch (change.changeType) {
        case 'created': {
          const name = path.split('/').pop() || path;

          if (parentPath) {
            const parts = parentPath.split('/');
            for (let i = 0; i < parts.length; i++) {
              const ancestorPath = parts.slice(0, i + 1).join('/');
              const ancestorParent = i === 0 ? '' : parts.slice(0, i).join('/');
              const ancestorName = parts[i];
              fileTree.insertNode(ancestorParent, {
                type: 'directory', name: ancestorName, path: ancestorPath, children: [],
              });
            }
            fileTree.setExpandedFolders((prev) => {
              const next = new Set(prev);
              for (let i = 0; i < parts.length; i++) {
                next.add(parts.slice(0, i + 1).join('/'));
              }
              return next;
            });
          }

          if (change.isDirectory) {
            fileTree.insertNode(parentPath, { type: 'directory', name, path, children: [] });
          } else {
            fileTree.insertNode(parentPath, { type: 'file', name, path });
          }
          fileTree.scheduleRefreshFolderList(parentPath);
          break;
        }
        case 'deleted': {
          fileTree.removeNode(path);
          fileTree.scheduleRefreshFolderList(parentPath);
          fileTabs.setFileCache((prev) => {
            const next = { ...prev };
            for (const key of Object.keys(next)) {
              const k = norm(key);
              if (k === path || k.startsWith(path + '/')) delete next[key];
            }
            return next;
          });
          fileTabs.setOpenTabs((prev) => {
            const next = prev.filter((t) => {
              const tp = norm(t.path);
              return tp !== path && !tp.startsWith(path + '/');
            });
            if (next.length !== prev.length) {
              fileTabs.setCurrentFilePath((cur) => {
                const cp = cur ? norm(cur) : '';
                if (cp === path || cp.startsWith(path + '/')) {
                  return next.length ? next[next.length - 1].path : null;
                }
                return cur;
              });
            }
            return next;
          });
          break;
        }
        case 'updated': {
          // Skip re-reading files we just saved locally (avoids redundant GET).
          if (fileContent.wasRecentlySaved(path)) break;
          const isModified = fileCacheRef.current[path]?.modified;
          if (!isModified) {
            fileTabs.setFileCache((prev) => {
              if (!prev[path]) return prev;
              const next = { ...prev };
              delete next[path];
              return next;
            });
            if (currentFilePathRef.current && norm(currentFilePathRef.current) === path) {
              fileContent.loadFileContent(path);
            }
          }
          break;
        }
        case 'renamed': {
          const oldPath = change.oldPath ? norm(change.oldPath) : '';
          if (oldPath) {
            fileTree.renameNodeInTree(oldPath, path);
            const oldParent = oldPath.includes('/') ? oldPath.split('/').slice(0, -1).join('/') : '';
            fileTree.scheduleRefreshFolderList(oldParent);
            if (parentPath !== oldParent) fileTree.scheduleRefreshFolderList(parentPath);
            fileTabs.setFileCache((prev) => {
              const next = { ...prev };
              if (next[oldPath]) {
                next[path] = next[oldPath];
                delete next[oldPath];
              }
              return next;
            });
            const newName = path.split('/').pop() || path;
            fileTabs.setOpenTabs((prev) =>
              prev.map((t) =>
                norm(t.path) === oldPath ? { ...t, path, name: newName } : t
              )
            );
            fileTabs.setCurrentFilePath((cur) =>
              cur && norm(cur) === oldPath ? path : cur
            );
          }
          break;
        }
      }
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useFileWatch(handleFileChanges);

  const resize = useResize();
  const [showLeftBar, setShowLeftBar] = useState(true);
  const [showAgentPanel, setShowAgentPanel] = useState(false);
  const leftBarVisible = showLeftBar;
  const rightBarVisible = showAgentPanel;
  const outputPanelVisible = resize.editorFlex < 100;

  const handleCloseTab = useCallback(
    (path: string) => {
      const cached = fileTabs.fileCache[path];
      if (cached?.modified && !confirm(`"${path.split('/').pop()}" has unsaved changes. Close anyway?`)) return;
      fileTabs.closeTab(path);
    },
    [fileTabs.fileCache, fileTabs.closeTab]
  );

  useKeyboardShortcuts({
    saveAllFiles: fileContent.saveAllFiles,
    openSearchTab: search.openSearchTab,
    closeTab: handleCloseTab,
    currentFilePath: fileTabs.currentFilePath,
    treeCreateMode: fileTree.treeCreateMode,
    cancelCreate: fileTree.cancelCreate,
    setContextMenu: fileTree.setContextMenu as (arg: unknown) => void,
    setRenameNode: fileTree.setRenameNode as (arg: unknown) => void,
    fileCache: fileTabs.fileCache,
    chatLoading: chat.chatLoading,
  });

  useEffect(() => {
    if (!fileTree.contextMenu.show) return;
    function onPointerDown(e: MouseEvent) {
      const el = contextMenuRef.current;
      if (el && !el.contains(e.target as Node)) fileTree.setContextMenu((prev) => ({ ...prev, show: false }));
    }
    document.addEventListener('mousedown', onPointerDown);
    return () => document.removeEventListener('mousedown', onPointerDown);
  }, [fileTree.contextMenu.show, fileTree.setContextMenu]);

  const modifiedCount = useMemo(
    () => Object.values(fileTabs.fileCache).filter((v) => v.modified).length,
    [fileTabs.fileCache]
  );

  const handleRun = () => {
    runCode.runCode(fileContent.codeValue, fileTabs.currentFilePath);
  };

  return (
    <>
      <Header
        leftBarVisible={leftBarVisible}
        onToggleLeftBar={() => setShowLeftBar((v) => !v)}
        outputPanelVisible={outputPanelVisible}
        onToggleOutputPanel={() => resize.setEditorFlex(resize.editorFlex >= 100 ? 65 : 100)}
        agentPanelVisible={rightBarVisible}
        onToggleAgentPanel={() => setShowAgentPanel((v) => !v)}
      />
      <div className="container">
        <FileTreeSidebar
          width={leftBarVisible ? resize.fileTreeWidth : 0}
          leftBarTab={search.leftBarTab}
          setLeftBarTab={search.setLeftBarTab}
          openSearchTab={search.openSearchTab}
          searchPattern={search.searchPattern}
          setSearchPattern={search.setSearchPattern}
          searchResults={search.searchResults}
          searchInputRef={search.searchInputRef}
          fileTreeData={fileTree.fileTreeData}
          expandedFolders={fileTree.expandedFolders}
          selectedTreePath={fileTree.selectedTreePath}
          treeCreateMode={fileTree.treeCreateMode}
          treeCreateParentPath={fileTree.treeCreateParentPath}
          treeCreateBeforePath={fileTree.treeCreateBeforePath}
          treeCreateInput={fileTree.treeCreateInput}
          renameNode={fileTree.renameNode}
          renameValue={fileTree.renameValue}
          initialExpandDoneRef={fileTree.initialExpandDoneRef}
          openTabs={fileTabs.openTabs}
          chatLoading={chat.chatLoading}
          modifiedCount={modifiedCount}
          loadFileTree={fileTree.loadFileTree}
          toolbarNewFile={fileTree.toolbarNewFile}
          toolbarNewFolder={fileTree.toolbarNewFolder}
          saveAllFiles={fileContent.saveAllFiles}
          toggleFolder={fileTree.toggleFolder}
          setSelectedTreePath={fileTree.setSelectedTreePath}
          setSelectedFolder={fileTree.setSelectedFolder}
          setContextMenu={fileTree.setContextMenu}
          hasCopied={!!fileTree.copiedFilePath}
          setTreeCreateInput={fileTree.setTreeCreateInput}
          setRenameValue={fileTree.setRenameValue}
          onRenameBlur={fileTree.handleRenameBlur}
          onRenameKeyDown={fileTree.handleRenameKeyDown}
          onCreateBlur={fileTree.handleCreateBlur}
          onCreateKeyDown={fileTree.handleCreateKeyDown}
          treeCreateInputRef={fileTree.treeCreateInputRef}
          renameInputRef={fileTree.renameInputRef}
          addTab={fileTabs.addTab}
          switchTab={fileTabs.switchTab}
          loadFileContent={fileContent.loadFileContent}
        />

        {leftBarVisible && (
          <Resizer kind="file" resizing={resize.resizing} onMouseDown={resize.startResizeFile} />
        )}

        <div className="main-content" ref={resize.mainContentRef}>
          <EditorSection
            editorFlex={resize.editorFlex}
            openTabs={fileTabs.openTabs}
            currentFilePath={fileTabs.currentFilePath}
            fileCache={fileTabs.fileCache}
            codeValue={fileContent.codeValue}
            onCodeChange={fileContent.handleCodeChange}
            runBusy={runCode.runBusy}
            chatLoading={chat.chatLoading}
            onSwitchTab={fileTabs.switchTab}
            onCloseTab={handleCloseTab}
            onRun={handleRun}
            pendingDiffs={diffReview.pendingDiffs}
            reviewIndex={diffReview.reviewIndex}
            onSetReviewIndex={diffReview.setReviewIndex}
            onAcceptDiff={diffReview.acceptDiff}
            onRejectDiff={diffReview.rejectDiff}
            onAcceptAll={diffReview.acceptAll}
            onRejectAll={diffReview.rejectAll}
          />
          <Resizer kind="editor" resizing={resize.resizing} onMouseDown={resize.startResizeEditor} title="Kéo để đổi chiều cao" />
          <OutputSection
            editorFlex={resize.editorFlex}
            outputTab={terminal.outputTab}
            outputHtml={runCode.outputHtml}
            terminalError={terminal.terminalError}
            terminalContainerRef={terminal.terminalContainerRef}
            setTerminalError={terminal.setTerminalError}
            onOutputTab={() => terminal.setOutputTab('output')}
            onTerminalTab={terminal.openTerminalTab}
            onClosePanel={() => resize.setEditorFlex(100)}
          />
        </div>

        {rightBarVisible && (
          <Resizer kind="chat" resizing={resize.resizing} onMouseDown={resize.startResizeRight} />
        )}

        <RightBar
          width={rightBarVisible ? resize.rightBarWidth : 0}
          sessions={chat.chatSessions}
          activeSessionId={chat.activeSessionId}
          onSwitchSession={chat.switchChatSession}
          onCloseSession={chat.closeChatSession}
          onAddSession={chat.addChatSession}
          messages={chat.chatMessages}
          loading={chat.chatLoading}
          chatMessagesContainerRef={chat.chatMessagesContainerRef}
          chatInputRef={chat.chatInputRef}
          userAtBottomRef={chat.userAtBottomRef}
          onSend={chat.sendChat}
          onStop={chat.stopChat}
        />
      </div>

      <Footer />

      <ContextMenu
        menu={fileTree.contextMenu}
        menuRef={contextMenuRef}
        onAction={fileTree.handleContextMenuAction}
      />
    </>
  );
}
