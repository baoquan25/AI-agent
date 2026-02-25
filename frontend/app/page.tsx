'use client';

import { useRef, useEffect } from 'react';
import { Header } from '../components/layout/Header';
import { Footer } from '../components/layout/Footer';
import { Resizer } from '../components/layout/Resizer';
import { FileTreeSidebar } from '../components/sidebar/FileTreeSidebar';
import { ContextMenu } from '../components/sidebar/ContextMenu';
import { EditorSection } from '../components/editor/EditorSection';
import { OutputSection } from '../components/output/OutputSection';
import { ChatSection } from '../components/agent/ChatSection';
import { useFileTabs } from '../hooks/useFileTabs';
import { useRunCode } from '../hooks/useRunCode';
import { useFileContent } from '../hooks/useFileContent';
import { useSearch } from '../hooks/useSearch';
import { useTerminal } from '../hooks/useTerminal';
import { useChat } from '../hooks/useChat';
import { useFileTree } from '../hooks/useFileTree';
import { useResize } from '../hooks/useResize';
import { useKeyboardShortcuts } from '../hooks/useKeyboardShortcuts';

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
  const chat = useChat(runCode.setOutputHtml, terminal.setOutputTab, () => loadFileTreeRef.current());

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

  const resize = useResize();

  const handleCloseTab = (path: string) => {
    const cached = fileTabs.fileCache[path];
    if (cached?.modified && !confirm(`"${path.split('/').pop()}" has unsaved changes. Close anyway?`)) return;
    fileTabs.closeTab(path);
  };

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

  const modifiedCount = Object.values(fileTabs.fileCache).filter((v) => v.modified).length;

  const handleRun = () => {
    runCode.runCode(fileContent.codeValue, fileTabs.currentFilePath);
  };

  return (
    <>
      <Header />
      <div className="container">
        <FileTreeSidebar
          width={resize.fileTreeWidth}
          sidebarTab={search.sidebarTab}
          setSidebarTab={search.setSidebarTab}
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

        <Resizer kind="file" resizing={resize.resizing} onMouseDown={resize.startResizeFile} />

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

        <Resizer kind="chat" resizing={resize.resizing} onMouseDown={resize.startResizeChat} />

        <ChatSection
          width={resize.chatSectionWidth}
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
