'use client';

import type { ChatMessage } from '../../lib/types';
import { ChatMessages } from './ChatMessages';
import { ChatInput } from './ChatInput';

type ChatSectionProps = {
  width: number;
  messages: ChatMessage[];
  loading: boolean;
  chatMessagesContainerRef: React.RefObject<HTMLDivElement | null>;
  chatInputRef: React.RefObject<HTMLTextAreaElement | null>;
  userAtBottomRef: React.MutableRefObject<boolean>;
  onSend: () => void;
  onStop: () => void;
};

export function ChatSection(props: ChatSectionProps) {
  const {
    width,
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
    const threshold = 80;
    userAtBottomRef.current = el.scrollTop + el.clientHeight >= el.scrollHeight - threshold;
  };

  return (
    <div
      className="section"
      id="chatSection"
      style={{ width, minWidth: 200, flex: 'none', display: 'flex', flexDirection: 'column', overflow: 'hidden' }}
    >
      <ChatMessages messages={messages} containerRef={chatMessagesContainerRef} onScroll={handleScroll} />
      <ChatInput inputRef={chatInputRef} loading={loading} onSend={onSend} onStop={onStop} />
    </div>
  );
}
