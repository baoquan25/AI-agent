'use client';

import type { ChatMessage } from '../../lib/types';
import { VscError } from '../../lib/icons';

type ChatMessagesProps = {
  messages: ChatMessage[];
  containerRef: React.RefObject<HTMLDivElement | null>;
  onScroll: () => void;
};

export function ChatMessages({ messages, containerRef, onScroll }: ChatMessagesProps) {
  return (
    <div id="chatMessages" ref={containerRef as React.RefObject<HTMLDivElement>} onScroll={onScroll}>
      {messages.map((msg, i) =>
        msg.sender === 'user' ? (
          <div key={i} className="chat-bubble user">
            {msg.text}
          </div>
        ) : (
          <div key={i} className={`chat-ai-text ${msg.isThinking ? 'thinking' : ''}`}>
            {msg.text}
            {msg.icon === 'error' && msg.text !== 'No connection' && <span style={{ marginLeft: 6, color: 'var(--error, #c00)', display: 'inline-flex', verticalAlign: 'middle' }}><VscError size={14} /></span>}
          </div>
        )
      )}
    </div>
  );
}
