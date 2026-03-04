import { AGENT_BASE } from '../constants';
import { apiHeaders } from '../utils';

export async function createConversation(): Promise<string> {
  const res = await fetch(`${AGENT_BASE}/conversation/`, {
    method: 'POST',
    headers: apiHeaders(),
  });
  if (!res.ok) throw new Error(`Failed to create conversation: ${res.status}`);
  const data = await res.json();
  return data.conversation_id as string;
}

export async function sendConversationMessage(
  conversationId: string,
  message: string,
  signal?: AbortSignal
): Promise<Response> {
  return fetch(`${AGENT_BASE}/conversation/${conversationId}/chat`, {
    method: 'POST',
    headers: apiHeaders(),
    body: JSON.stringify({ message }),
    signal,
  });
}

export async function deleteConversation(conversationId: string): Promise<void> {
  await fetch(`${AGENT_BASE}/conversation/${conversationId}`, {
    method: 'DELETE',
    headers: apiHeaders(),
  });
}
