'use client';

import { useState, useCallback, useRef, useEffect, useMemo } from 'react';
import { useStream } from '@langchain/langgraph-sdk/react';
import type { ChatMessage, FileEdit } from '../lib/types';
import { AGENT_BASE } from '../lib/constants';
import { getUserId, escapeHtml, stripAnsi } from '../lib/utils';
import { deleteConversation } from '../lib/api/agent';

type SetOutputHtml = (html: string) => void;
type SetOutputTab = (tab: 'output' | 'terminal') => void;
type OnFileEdits = (edits: FileEdit[]) => void;

type CodeOutput = {
  file_path?: string;
  output?: string;
  exit_code?: number;
  success?: boolean;
  outputs?: Array<{ type?: string; data?: string; library?: string }>;
};

function renderCodeOutputs(items: CodeOutput[]): string {
  let html = '';
  for (const item of items) {
    const isError = item.success === false || (item.exit_code ?? 0) !== 0;
    const textOut = item.output ?? '';
    if (textOut) {
      const pre = `<pre class="output-stdout">${escapeHtml(stripAnsi(textOut))}</pre>`;
      html += isError ? `<div class="output-error">${pre}</div>` : pre;
    }
    const richList = item.outputs ?? [];
    richList.forEach((r, i) => {
      const type = r.type ?? '';
      const d = r.data ?? '';
      const lib = r.library ?? '';
      if (type.startsWith('image/'))
        html += `<div class="rich-output-item"><div class="rich-output-label"><span class="codicon codicon-graph"></span> ${lib || 'Chart'} ${i + 1}</div><img src="data:${type};base64,${d}" alt="Output" /></div>`;
      else if (type === 'text/html')
        html += `<div class="rich-output-item"><div class="rich-output-label"> </div><div class="rich-output-html">${d}</div></div>`;
      else if (type === 'image/svg+xml')
        html += `<div class="rich-output-item"><div class="rich-output-label"><span class="codicon codicon-paintcan"></span> SVG ${i + 1}</div><div style="background:white;padding:10px;">${d}</div></div>`;
    });
  }
  return html || '<span class="output-success">Done</span>';
}

type Session = { id: string; threadId?: string };
export type ChatSession = { id: string; messages: ChatMessage[]; loading: boolean };

function genId() {
  return Math.random().toString(36).slice(2, 10);
}

function extractText(content: unknown): string {
  if (typeof content === 'string') return content;
  if (Array.isArray(content)) {
    return content
      .filter((c): c is { type: string; text: string } => typeof c === 'object' && c?.type === 'text')
      .map((c) => c.text)
      .join('');
  }
  return '';
}

export function useChat(
  setOutputHtml: SetOutputHtml,
  setOutputTab: SetOutputTab,
  _loadFileTree: () => Promise<void>,
  onFileEdits?: OnFileEdits,
) {
  const [sessions, setSessions] = useState<Session[]>([]);
  const [activeIdx, setActiveIdx] = useState<number>(0);
  const [messagesMap, setMessagesMap] = useState<Record<string, ChatMessage[]>>({});
  const chatInputRef = useRef<HTMLTextAreaElement>(null);
  const chatMessagesContainerRef = useRef<HTMLDivElement>(null);
  const userAtBottomRef = useRef(true);

  const activeIdxRef = useRef(activeIdx);
  activeIdxRef.current = activeIdx;

  const activeSession = sessions[activeIdx] ?? null;

  const onThreadId = useCallback((threadId: string) => {
    const idx = activeIdxRef.current;
    setSessions((prev) => prev.map((s, i) => (i === idx ? { ...s, threadId } : s)));
  }, []);

  const activeThreadId = activeSession?.threadId ?? undefined;
  const streamConfig = useMemo(() => ({
    apiUrl: `${AGENT_BASE}/conversation`,
    apiKey: getUserId(),
    assistantId: 'agent' as const,
    threadId: activeThreadId,
    onThreadId,
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }), [activeThreadId, onThreadId]);

  const stream = useStream(streamConfig);

  // Sync stream → messagesMap only when actual content changes.
  // Comparing by length + last message id avoids:
  //  1) infinite loops (stream.messages is a new array each render)
  //  2) stale writes on tab switch (old data produces the same key)
  const prevKeyRef = useRef('');
  useEffect(() => {
    const len = stream.messages.length;
    const last: any = len > 0 ? stream.messages[len - 1] : null;
    const key = `${len}:${last?.id ?? ''}:${last ? extractText(last.content).length : 0}`;
    if (key === prevKeyRef.current) return;
    prevKeyRef.current = key;
    if (!activeSession?.id) return;
    if (len === 0) return;
    const msgs: ChatMessage[] = stream.messages.map((m) => ({
      sender: m.type === 'human' ? ('user' as const) : ('ai' as const),
      text: extractText(m.content),
    }));
    setMessagesMap((prev) => ({ ...prev, [activeSession.id]: msgs }));
  }, [stream.messages, activeSession?.id]);

  // Render agent-triggered code outputs into the Output panel.
  const prevCodeOutputsKeyRef = useRef('');
  useEffect(() => {
    const codeOutputs = (stream.values as Record<string, unknown> | null)?.code_outputs;
    if (!Array.isArray(codeOutputs) || codeOutputs.length === 0) return;
    const key = JSON.stringify(codeOutputs.map((o: CodeOutput) => o.output).join('|'));
    if (key === prevCodeOutputsKeyRef.current) return;
    prevCodeOutputsKeyRef.current = key;
    const html = renderCodeOutputs(codeOutputs as CodeOutput[]);
    setOutputHtml(html);
    setOutputTab('output');
  }, [stream.values, setOutputHtml, setOutputTab]);

  const onFileEditsRef = useRef(onFileEdits);
  onFileEditsRef.current = onFileEdits;

  const prevEditsIdRef = useRef('');
  useEffect(() => {
    const vals = stream.values as Record<string, unknown> | null;
    const editsId = (vals?._file_edits_id as string) ?? '';
    if (!editsId || editsId === prevEditsIdRef.current) return;
    const fileEdits = vals?.file_edits;
    if (!Array.isArray(fileEdits) || fileEdits.length === 0) return;
    prevEditsIdRef.current = editsId;
    onFileEditsRef.current?.(fileEdits as FileEdit[]);
  }, [stream.values]);

  const displayMessages = messagesMap[activeSession?.id ?? ''] ?? [];
  const lastSender = displayMessages[displayMessages.length - 1]?.sender;
  const showThinking = stream.isLoading && (displayMessages.length === 0 || lastSender === 'user');
  const errorMsg = stream.error ? `Error: ${(stream.error as Error)?.message ?? String(stream.error)}` : null;

  const chatMessages = useMemo<ChatMessage[]>(() => [
    ...displayMessages,
    ...(showThinking ? [{ sender: 'ai' as const, text: 'Thinking...', isThinking: true }] : []),
    ...(errorMsg ? [{ sender: 'ai' as const, text: errorMsg, icon: 'error' as const }] : []),
  // displayMessages reference only changes when setMessagesMap is called (stable via key check above)
  // eslint-disable-next-line react-hooks/exhaustive-deps
  ], [displayMessages, showThinking, errorMsg]);

  const chatLoading = stream.isLoading;

  const chatSessions: ChatSession[] = sessions.map((s, i) => ({
    id: s.id,
    messages: i === activeIdx ? chatMessages : (messagesMap[s.id] ?? []),
    loading: i === activeIdx ? chatLoading : false,
  }));

  const activeSessionId = activeSession?.id ?? null;

  const addChatSession = useCallback(() => {
    const newSession: Session = { id: genId() };
    setSessions((prev) => {
      const next = [...prev, newSession];
      setActiveIdx(next.length - 1);
      return next;
    });
  }, []);

  const switchChatSession = useCallback((id: string) => {
    setSessions((prev) => {
      const idx = prev.findIndex((s) => s.id === id);
      if (idx !== -1) setActiveIdx(idx);
      return prev;
    });
  }, []);

  const closeChatSession = useCallback((id: string) => {
    setSessions((prev) => {
      const idx = prev.findIndex((s) => s.id === id);
      if (idx === -1) return prev;
      const s = prev[idx];
      if (s.threadId) deleteConversation(s.threadId).catch(() => {});
      setMessagesMap((m) => { const n = { ...m }; delete n[s.id]; return n; });
      const next = prev.filter((_, i) => i !== idx);
      setActiveIdx((cur) => {
        if (cur === idx) return Math.max(0, idx - 1);
        if (cur > idx) return cur - 1;
        return cur;
      });
      return next;
    });
  }, []);

  const sendChat = useCallback(() => {
    const ta = chatInputRef.current;
    if (!ta || !activeSession) return;
    const text = ta.value.trim();
    if (!text || stream.isLoading) return;
    ta.value = '';
    const humanMsg = { type: 'human' as const, content: text };
    stream.submit(
      { messages: [humanMsg] },
      {
        optimisticValues: (prev: Record<string, unknown>) => ({
          ...prev,
          messages: [...((prev.messages as unknown[]) ?? []), humanMsg],
        }),
      }
    );
  }, [activeSession, stream]);

  const stopChat = useCallback(() => {
    stream.stop();
  }, [stream]);

  const chatMessagesLenRef = useRef(0);
  useEffect(() => {
    if (chatMessages.length === chatMessagesLenRef.current) return;
    chatMessagesLenRef.current = chatMessages.length;
    if (!userAtBottomRef.current) return;
    const el = chatMessagesContainerRef.current;
    if (el) el.scrollTop = el.scrollHeight;
  // chatMessages is memoized so reference is stable between renders with same content
  }, [chatMessages]);

  return {
    chatSessions,
    activeSessionId,
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
