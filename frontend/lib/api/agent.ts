import { AGENT_BASE } from '../constants';
import { apiHeaders } from '../utils';

/** Delete a thread/conversation by its ID (threadId from useStream or legacy conversationId). */
export async function deleteConversation(id: string): Promise<void> {
  // Try the new /threads endpoint first, fall back to legacy /conversation
  await fetch(`${AGENT_BASE}/conversation/threads/${id}`, {
    method: 'DELETE',
    headers: apiHeaders(),
  }).catch(() => {});
  await fetch(`${AGENT_BASE}/conversation/${id}`, {
    method: 'DELETE',
    headers: apiHeaders(),
  }).catch(() => {});
}
