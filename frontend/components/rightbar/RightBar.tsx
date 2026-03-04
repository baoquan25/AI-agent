'use client';

import type { ChatMessage } from '../../lib/types';
import type { ChatSession } from '../../hooks/useChat';
import { ChatMessages } from './ChatMessages';
import { ChatInput } from './ChatInput';

type RightBarProps = {
  width: number;
  sessions: ChatSession[];
  activeSessionId: string | null;
  onSwitchSession: (id: string) => void;
  onCloseSession: (id: string) => void;
  onAddSession: () => void;
  messages: ChatMessage[];
  loading: boolean;
  chatMessagesContainerRef: React.RefObject<HTMLDivElement | null>;
  chatInputRef: React.RefObject<HTMLTextAreaElement | null>;
  userAtBottomRef: React.MutableRefObject<boolean>;
  onSend: () => void;
  onStop: () => void;
};

export function RightBar(props: RightBarProps) {
  const {
    width,
    sessions,
    activeSessionId,
    onSwitchSession,
    onCloseSession,
    onAddSession,
    messages,
    loading,
    chatMessagesContainerRef,
    chatInputRef,
    userAtBottomRef,
    onSend,
    onStop,
  } = props;

  const handleScroll = () => {
    const el = chatMessagesContainerRef.current;
    if (!el) return;
    userAtBottomRef.current = el.scrollTop + el.clientHeight >= el.scrollHeight - 80;
  };

  return (
    <div
      id="rightBar"
      style={{ width, minWidth: sessions.length > 0 ? 200 : 0, flex: 'none', display: 'flex', flexDirection: 'column', overflow: 'hidden' }}
    >
      <div className="rightbar-tabs-bar">
        <div className="rightbar-tabs">
          {sessions.map((s, i) => (
            <div
              key={s.id}
              role="tab"
              tabIndex={0}
              className={`rightbar-tab ${s.id === activeSessionId ? 'active' : ''}`}
              onClick={() => onSwitchSession(s.id)}
              onKeyDown={(e) => {
                if (e.key === 'Enter' || e.key === ' ') onSwitchSession(s.id);
              }}
            >
              <span className="rightbar-tab-name">Chat {i + 1}</span>
              <button
                type="button"
                className="rightbar-tab-close"
                onClick={(e) => { e.stopPropagation(); onCloseSession(s.id); }}
                title="Đóng conversation"
                aria-label="Đóng conversation"
              >
                <span className="codicon codicon-close" />
              </button>
            </div>
          ))}
        </div>
        <button
          type="button"
          className="rightbar-tab-add"
          onClick={onAddSession}
          title="Tạo conversation mới"
          aria-label="Tạo conversation mới"
        >
          <span className="codicon codicon-add" />
        </button>
      </div>

      {sessions.length === 0 ? (
        <div className="rightbar-empty">
          <button type="button" className="rightbar-empty-btn" onClick={onAddSession}>
            + New conversation
          </button>
        </div>
      ) : (
        <div key={activeSessionId} className="rightbar-session">
          <ChatMessages messages={messages} containerRef={chatMessagesContainerRef} onScroll={handleScroll} />
          <ChatInput inputRef={chatInputRef} loading={loading} onSend={onSend} onStop={onStop} />
        </div>
      )}
    </div>
  );
}
