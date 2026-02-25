'use client';

import { useState, useCallback, useRef, useEffect } from 'react';
import { flushSync } from 'react-dom';
import type { ChatMessage } from '../lib/types';
import { sendChatMessage } from '../lib/api/agent';
import { escapeHtml, stripAnsi } from '../lib/utils';

type SetOutputHtml = (html: string) => void;
type SetOutputTab = (tab: 'output' | 'terminal') => void;

function buildOutputItemHtml(
  item: {
    success?: boolean;
    file_path?: string;
    output?: string;
    exit_code?: number;
    outputs?: Array<{ type?: string; data?: string; library?: string }>;
  },
  index: number
): string {
  let html = '';
  const label = item.file_path ? `Agent ran: ${item.file_path}` : 'Agent executed code';
  const cls = item.success ? 'output-success' : 'output-error';
  if (index > 0) html += '<hr class="output-divider">';
  html += `<div style="margin-bottom:4px;"><span class="${cls}">${escapeHtml(label)} (exit: ${item.exit_code ?? ''})</span></div>`;
  if (item.output) html += `<pre class="output-stdout">${escapeHtml(stripAnsi(item.output))}</pre>`;
  const richList = item.outputs ?? [];
  if (Array.isArray(richList) && richList.length > 0) {
    richList.forEach((r, ri) => {
      const type = r.type || '', d = r.data || '', lib = r.library || '';
      if (type.startsWith('image/')) html += `<div class="rich-output-item"><div class="rich-output-label"><span class="codicon codicon-graph"></span> ${lib || 'Chart'} ${ri + 1}</div><img src="data:${type};base64,${d}" alt="Output" /></div>`;
      else if (type === 'text/html') html += `<div class="rich-output-item"><div class="rich-output-label">${lib || 'HTML'} ${ri + 1}</div><div class="rich-output-html">${d}</div></div>`;
      else if (type === 'image/svg+xml') html += `<div class="rich-output-item"><div class="rich-output-label"><span class="codicon codicon-paintcan"></span> SVG ${ri + 1}</div><div style="background:white;padding:10px;">${d}</div></div>`;
    });
  }
  return html;
}

export function useChat(
  setOutputHtml: SetOutputHtml,
  setOutputTab: SetOutputTab,
  loadFileTree: () => Promise<void>
) {
  const [chatMessages, setChatMessages] = useState<ChatMessage[]>([]);
  const [chatLoading, setChatLoading] = useState(false);
  const chatInputRef = useRef<HTMLTextAreaElement>(null);
  const chatMessagesContainerRef = useRef<HTMLDivElement>(null);
  const userAtBottomRef = useRef(true);
  const chatAbortRef = useRef<AbortController | null>(null);

  const sendChat = useCallback(async () => {
    const ta = chatInputRef.current;
    if (!ta) return;
    const text = ta.value.trim();
    if (!text || chatLoading) return;
    setChatMessages((prev) => [...prev, { sender: 'user', text }, { sender: 'ai', text: 'Thinking...', isThinking: true }]);
    ta.value = '';
    setChatLoading(true);
    chatAbortRef.current = new AbortController();
    try {
      const res = await sendChatMessage(text, chatAbortRef.current.signal);
      if (!res.ok) {
        if (res.status === 404) throw new Error('No connection');
        throw new Error(`Agent lỗi: ${res.status} ${res.statusText}`);
      }
      const contentType = res.headers.get('content-type') || '';
      const isStream = contentType.includes('text/event-stream');
      if (isStream) {
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
              try {
                const obj = JSON.parse(dataLine);
                streamedText = obj.error || 'Agent failed';
              } catch {
                streamedText = dataLine;
              }
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
                      const withoutThinking = prev.filter((m) => !m.isThinking);
                      const withoutLastAi = withoutThinking.length && withoutThinking[withoutThinking.length - 1].sender === 'ai' ? withoutThinking.slice(0, -1) : withoutThinking;
                      return [...withoutLastAi, { sender: 'ai', text: streamedText }];
                    });
                  });
                }
              } catch {
                /* skip */
              }
            }
          }
          if (hasError) break;
        }
        const finalText = streamedText || 'Xong.';
        setChatMessages((prev) => {
          const withoutThinking = prev.filter((m) => !m.isThinking);
          const withoutLastAi = withoutThinking.length && withoutThinking[withoutThinking.length - 1].sender === 'ai' ? withoutThinking.slice(0, -1) : withoutThinking;
          return [...withoutLastAi, { sender: 'ai', text: finalText, icon: hasError ? 'error' : 'success' }];
        });
      } else {
        const data = await res.json().catch(() => ({}));
        const reply = data.agent_reply ?? data.reply ?? data.message ?? (data.error ? String(data.error) : '');
        const codeOutputs = data.code_outputs ?? data.results ?? [];
        if (Array.isArray(codeOutputs) && codeOutputs.length > 0) {
          let html = '';
          codeOutputs.forEach((item: Parameters<typeof buildOutputItemHtml>[0], i: number) => {
            html += buildOutputItemHtml(item, i);
          });
          setOutputHtml(html || '<span class="output-success">Done</span>');
          setOutputTab('output');
        }
        setChatMessages((prev) => prev.filter((m) => !m.isThinking).concat([{ sender: 'ai', text: reply || 'Done.', icon: data.error ? 'error' : 'success' }]));
      }
      await loadFileTree();
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
  }, [chatLoading, setOutputHtml, setOutputTab, loadFileTree]);

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
  }, []);

  useEffect(() => {
    if (!userAtBottomRef.current) return;
    const el = chatMessagesContainerRef.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [chatMessages]);

  return {
    chatMessages,
    chatLoading,
    sendChat,
    stopChat,
    chatInputRef,
    chatMessagesContainerRef,
    userAtBottomRef,
  };
}
