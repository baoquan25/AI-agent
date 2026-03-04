'use client';

import { useState, useCallback } from 'react';
import { API_BASE } from '../lib/constants';
import { apiHeaders } from '../lib/utils';
import { escapeHtml, stripAnsi } from '../lib/utils';
type RunResponse = {
  success?: boolean;
  output?: string;
  stdout?: string;
  detail?: string;
  outputs?: Array<{ type?: string; data?: string; library?: string; lib?: string }>;
  rich_output?: Array<{ type?: string; data?: string; library?: string; lib?: string }>;
};

export function useRunCode() {
  const [runBusy, setRunBusy] = useState(false);
  const [outputHtml, setOutputHtml] = useState('');

  const runCode = useCallback(async (codeValue: string, currentFilePath: string | null) => {
    setRunBusy(true);
    setOutputHtml('<span style="color:var(--muted)">Running...</span>');
    try {
      const payload = { code: codeValue, use_jupyter: true, file_path: currentFilePath || undefined };
      const res = await fetch(`${API_BASE}/run`, { method: 'POST', headers: apiHeaders(), body: JSON.stringify(payload) });
      const data: RunResponse = await res.json();
      if (!res.ok) {
        setOutputHtml(`<span class="output-error">${data.detail || 'Failed'}</span>`);
        setRunBusy(false);
        return;
      }
      let html = '';
      const isError = data.success === false;
      const textOut = data.output ?? data.stdout ?? '';
      if (textOut) {
        const pre = `<pre class="output-stdout">${escapeHtml(stripAnsi(textOut))}</pre>`;
        html += isError ? `<div class="output-error">${pre}</div>` : pre;
      }
      const richList = data.outputs ?? data.rich_output ?? [];
      if (Array.isArray(richList) && richList.length > 0) {
        richList.forEach((item: { type?: string; data?: string; library?: string; lib?: string }, i: number) => {
          const type = item.type || '';
          const d = item.data || '';
          const lib = item.library ?? item.lib ?? '';
          if (type.startsWith('image/')) html += `<div class="rich-output-item"><div class="rich-output-label"><span class="codicon codicon-graph"></span> ${lib || 'Chart'} ${i + 1}</div><img src="data:${type};base64,${d}" alt="Output" /></div>`;
          else if (type === 'text/html') html += `<div class="rich-output-item"><div class="rich-output-label"> </div><div class="rich-output-html">${d}</div></div>`;
          else if (type === 'image/svg+xml') html += `<div class="rich-output-item"><div class="rich-output-label"><span class="codicon codicon-paintcan"></span> SVG ${i + 1}</div><div style="background:white;padding:10px;">${d}</div></div>`;
        });
      }
      if (!html) html = isError ? '<span class="output-error">Execution failed</span>' : '<span class="output-success">Done</span>';
      setOutputHtml(html);
    } catch (e) {
      setOutputHtml(`<span class="output-error">${(e as Error).message}</span>`);
    }
    setRunBusy(false);
  }, []);

  return { runBusy, outputHtml, setOutputHtml, runCode };
}
