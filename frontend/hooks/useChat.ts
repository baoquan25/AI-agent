'use client';

import { useState, useCallback, useRef, useEffect } from 'react';
import { flushSync } from 'react-dom';
import type { ChatMessage } from '../lib/types';
import { createConversation, deleteConversation, sendConversationMessage } from '../lib/api/agent';

type SetOutputHtml = (html: string) => void;
type SetOutputTab = (tab: 'output' | 'terminal') => void;

export type ChatSession = { id: string; messages: ChatMessage[]; loading: boolean };

export function useChat(
  setOutputHtml: SetOutputHtml,
  setOutputTab: SetOutputTab,
  loadFileTree: () => Promise<void>
) {
  const [chatSessions, setChatSessions] = useState<ChatSession[]>([]);
  const [activeSessionId, setActiveSessionId] = useState<string | null>(null);
  const chatInputRef = useRef<HTMLTextAreaElement>(null);
  const chatMessagesContainerRef = useRef<HTMLDivElement>(null);
  const userAtBottomRef = useRef(true);
  const chatAbortRef = useRef<AbortController | null>(null);

  const activeId = activeSessionId ?? chatSessions[0]?.id ?? null;
  const activeSession = chatSessions.find((s) => s.id === activeId);
  const chatMessages = activeSession?.messages ?? [];
  const chatLoading = activeSession?.loading ?? false;

  // Tạo conversation mới trên backend → lấy UUID → thêm tab
  const addChatSession = useCallback(async () => {
    try {
      const conversationId = await createConversation();
      setChatSessions((prev) => [...prev, { id: conversationId, messages: [], loading: false }]);
      setActiveSessionId(conversationId);
    } catch (e) {
      console.error('Failed to create conversation:', e);
    }
  }, []);

  const switchChatSession = useCallback((id: string) => {
    setActiveSessionId(id);
  }, []);

  // Đóng tab: xóa local + gọi backend delete
  const closeChatSession = useCallback((id: string) => {
    setChatSessions((prev) => {
      const next = prev.filter((s) => s.id !== id);
      setActiveSessionId((current) => {
        if (current === id) return next[0]?.id ?? null;
        return current;
      });
      return next;
    });
    deleteConversation(id).catch(() => {});
  }, []);

  const setChatMessages = useCallback(
    (updater: (prev: ChatMessage[]) => ChatMessage[]) => {
      if (!activeId) return;
      setChatSessions((prev) =>
        prev.map((s) => (s.id === activeId ? { ...s, messages: updater(s.messages) } : s))
      );
    },
    [activeId]
  );

  const setChatLoading = useCallback(
    (loading: boolean) => {
      if (!activeId) return;
      setChatSessions((prev) =>
        prev.map((s) => (s.id === activeId ? { ...s, loading } : s))
      );
    },
    [activeId]
  );

  const sendChat = useCallback(async () => {
    const ta = chatInputRef.current;
    if (!ta || !activeId) return;
    const text = ta.value.trim();
    if (!text || chatLoading) return;
    setChatMessages((prev) => [...prev, { sender: 'user', text }, { sender: 'ai', text: 'Thinking...', isThinking: true }]);
    ta.value = '';
    setChatLoading(true);
    chatAbortRef.current = new AbortController();
    try {
      const res = await sendConversationMessage(activeId, text, chatAbortRef.current.signal);
      if (!res.ok) {
        if (res.status === 404) throw new Error('No connection');
        throw new Error(`Agent lỗi: ${res.status} ${res.statusText}`);
      }
      const reader = res.body?.getReader();
      if (!reader) throw new Error('No response stream');
      const decoder = new TextDecoder('utf-8');
      let buffer = '', streamedText = '', hasError = false;
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const parts = buffer.split('\n\n');
        buffer = parts.pop()!;
        for (const part of parts) {
          const lines = part.split('\n');
          let eventName = '';
          let dataLine = '';
          for (const line of lines) {
            if (line.startsWith('event:')) eventName = line.slice(6).trim();
            if (line.startsWith('data:')) dataLine += line.slice(5).trim();
          }
          if (eventName === 'done') break;
          if (eventName === 'error' && dataLine) {
            try { streamedText = JSON.parse(dataLine).error || 'Agent failed'; }
            catch { streamedText = dataLine; }
            hasError = true;
            break;
          }
          if (dataLine) {
            try {
              const obj = JSON.parse(dataLine);
              if (obj.text !== undefined) {
                streamedText += obj.text;
                flushSync(() => {
                  setChatMessages((prev) => {
                    const base = prev.filter((m) => !m.isThinking);
                    const withoutLastAi = base.length && base[base.length - 1].sender === 'ai' ? base.slice(0, -1) : base;
                    return [...withoutLastAi, { sender: 'ai', text: streamedText }];
                  });
                });
              }
            } catch { /* skip */ }
          }
        }
        if (hasError) break;
      }
      const finalText = streamedText || 'Xong.';
      setChatMessages((prev) => {
        const base = prev.filter((m) => !m.isThinking);
        const withoutLastAi = base.length && base[base.length - 1].sender === 'ai' ? base.slice(0, -1) : base;
        return [...withoutLastAi, { sender: 'ai', text: finalText, icon: hasError ? 'error' : 'success' }];
      });
      // Tree update handled by WebSocket file watcher — no need to poll
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : String(e);
      const isOffline = msg.includes('Failed to fetch') || msg.includes('NetworkError') || msg.includes('Load failed');
      const friendly = isOffline ? 'No connection' : msg;
      setChatMessages((prev) =>
        prev.filter((m) => !m.isThinking).concat([{ sender: 'ai', text: friendly, ...(friendly !== 'No connection' && { icon: 'error' as const }) }])
      );
    }
    setChatLoading(false);
    chatAbortRef.current = null;
  }, [activeId, chatLoading, loadFileTree, setChatMessages, setChatLoading]);

  const stopChat = useCallback(() => {
    if (chatAbortRef.current) {
      chatAbortRef.current.abort();
      chatAbortRef.current = null;
    }
    setChatMessages((prev) => {
      const withoutThinking = prev.filter((m) => !m.isThinking);
      const last = withoutThinking[withoutThinking.length - 1];
      if (last && last.sender === 'ai' && last.text) return withoutThinking;
      return [...withoutThinking, { sender: 'ai', text: '(Đã dừng)' }];
    });
    setChatLoading(false);
  }, [setChatMessages, setChatLoading]);

  useEffect(() => {
    if (!userAtBottomRef.current) return;
    const el = chatMessagesContainerRef.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [chatMessages]);

  return {
    chatSessions,
    activeSessionId: activeId,
    addChatSession,
    switchChatSession,
    closeChatSession,
    chatMessages,
    chatLoading,
    sendChat,
    stopChat,
    chatInputRef,
    chatMessagesContainerRef,
    userAtBottomRef,
  };
}
