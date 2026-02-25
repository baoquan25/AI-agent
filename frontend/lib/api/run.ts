import { API_BASE } from '../constants';
import { apiHeaders } from '../utils';

export type RunPayload = {
  code: string;
  use_jupyter?: boolean;
  file_path?: string;
};

export type RunResponse = {
  success?: boolean;
  output?: string;
  stdout?: string;
  detail?: string;
  outputs?: Array<{ type?: string; data?: string; library?: string; lib?: string }>;
  rich_output?: Array<{ type?: string; data?: string; library?: string; lib?: string }>;
};

export async function runCode(payload: RunPayload): Promise<RunResponse> {
  const res = await fetch(`${API_BASE}/run`, {
    method: 'POST',
    headers: apiHeaders(),
    body: JSON.stringify(payload),
  });
  return res.json();
}
