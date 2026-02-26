'use client';

import { useState, useRef, useEffect } from 'react';

export function useResize() {
  const [fileTreeWidth, setFileTreeWidth] = useState(270);
  const [chatSectionWidth, setChatSectionWidth] = useState(350);
  const [editorFlex, setEditorFlex] = useState(65);
  const [resizing, setResizing] = useState<'file' | 'chat' | 'editor' | null>(null);
  const resizeStartRef = useRef({ x: 0, y: 0, width: 0, height: 0 });
  const mainContentRef = useRef<HTMLDivElement>(null);
  const editorFlexRef = useRef(editorFlex);
  editorFlexRef.current = editorFlex;

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
        setFileTreeWidth(Math.max(80, Math.min(500, resizeStartRef.current.width + (e.clientX - resizeStartRef.current.x))));
      } else if (resizing === 'chat') {
        setChatSectionWidth(Math.max(200, resizeStartRef.current.width - (e.clientX - resizeStartRef.current.x)));
      } else if (resizing === 'editor') {
        const totalH = resizeStartRef.current.height;
        if (totalH <= 0) return;
        const deltaPct = ((e.clientY - resizeStartRef.current.y) / totalH) * 100;
        setEditorFlex(Math.max(15, Math.min(100, resizeStartRef.current.width + deltaPct)));
      }
    };
    const onUp = () => setResizing(null);
    document.body.style.cursor = resizing === 'editor' ? 'row-resize' : 'col-resize';
    document.body.style.userSelect = 'none';
    if (resizing === 'editor') document.body.classList.add('is-resizing-editor');
    document.addEventListener('mousemove', onMove);
    document.addEventListener('mouseup', onUp);
    return () => {
      document.removeEventListener('mousemove', onMove);
      document.removeEventListener('mouseup', onUp);
      document.body.style.cursor = '';
      document.body.style.userSelect = '';
      document.body.classList.remove('is-resizing-editor');
    };
  }, [resizing]);

  return {
    fileTreeWidth,
    chatSectionWidth,
    editorFlex,
    setEditorFlex,
    resizing,
    mainContentRef,
    startResizeFile,
    startResizeChat,
    startResizeEditor,
  };
}
