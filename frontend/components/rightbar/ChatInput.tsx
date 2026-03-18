'use client';

import { VscStopCircle } from '../../lib/icons';

type ChatInputProps = {
  inputRef: React.RefObject<HTMLTextAreaElement | null>;
  loading: boolean;
  onSend: () => void;
  onStop: () => void;
};

export function ChatInput({ inputRef, loading, onSend, onStop }: ChatInputProps) {
  return (
    <div className="chat-input-area">
      <textarea
        ref={inputRef as React.RefObject<HTMLTextAreaElement>}
        id="chatInput"
        placeholder="Ask AI..."
        rows={2}
        onKeyDown={(e) => {
          if (e.key === 'Enter' && !e.shiftKey) {
            if (loading) return;
            e.preventDefault();
            onSend();
          }
        }}
      />
      {loading && (
        <button type="button" className="chat-stop-btn" onClick={onStop} title="Stop AI" aria-label="Stop AI">
          <VscStopCircle size={22} aria-hidden />
        </button>
      )}
    </div>
  );
}
