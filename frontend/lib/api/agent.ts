import { AI_AGENT_URL } from '../constants';
import { apiHeaders } from '../utils';

export type ChatResponse = {
  agent_reply?: string;
  reply?: string;
  message?: string;
  error?: string;
  code_outputs?: Array<{
    success?: boolean;
    file_path?: string;
    output?: string;
    exit_code?: number;
    outputs?: Array<{ type?: string; data?: string; library?: string }>;
  }>;
  results?: Array<unknown>;
};

export async function sendChatMessage(message: string, signal?: AbortSignal): Promise<Response> {
  return fetch(AI_AGENT_URL, {
    method: 'POST',
    headers: apiHeaders(),
    body: JSON.stringify({ message }),
    signal,
  });
}
