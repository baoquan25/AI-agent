import { API_BASE } from '../constants';
import { apiHeaders } from '../utils';
import type { TreeNode } from '../types';

export async function loadTree(): Promise<TreeNode | null> {
  try {
    const res = await fetch(`${API_BASE}/fs/tree`, { headers: apiHeaders() });
    const data = await res.json();
    return data.success && data.tree ? data.tree : null;
  } catch {
    return null;
  }
}

export type ListFileItem = { name: string; path: string; type: 'file' | 'directory'; size?: number; modified?: string };

export async function loadList(path: string = ''): Promise<ListFileItem[] | null> {
  try {
    const q = path ? `?path=${encodeURIComponent(path)}` : '';
    const res = await fetch(`${API_BASE}/fs/list${q}`, { headers: apiHeaders() });
    const data = await res.json();
    return data.success && Array.isArray(data.files) ? data.files : null;
  } catch {
    return null;
  }
}

export async function getFileContent(path: string): Promise<{ success: boolean; content?: string; detail?: string }> {
  const res = await fetch(`${API_BASE}/fs/file/content?path=${encodeURIComponent(path)}`, { headers: apiHeaders() });
  return res.json();
}

export async function createFile(path: string, content: string = ''): Promise<{ success: boolean; detail?: string }> {
  const res = await fetch(`${API_BASE}/fs/file`, {
    method: 'POST',
    headers: apiHeaders(),
    body: JSON.stringify({ path, content }),
  });
  return res.json();
}

export async function createFolder(path: string): Promise<{ success: boolean; detail?: string }> {
  const res = await fetch(`${API_BASE}/fs/folder`, {
    method: 'POST',
    headers: apiHeaders(),
    body: JSON.stringify({ path }),
  });
  return res.json();
}

export async function deletePath(path: string, recursive: boolean = true): Promise<{ success: boolean; detail?: string }> {
  const res = await fetch(
    `${API_BASE}/fs/path?path=${encodeURIComponent(path)}&recursive=${recursive}`,
    { method: 'DELETE', headers: apiHeaders() }
  );
  return res.json();
}

export async function renamePath(source: string, destination: string): Promise<{ success: boolean; detail?: string }> {
  const res = await fetch(`${API_BASE}/fs/rename`, {
    method: 'POST',
    headers: apiHeaders(),
    body: JSON.stringify({ source, destination }),
  });
  return res.json();
}

export async function searchFiles(pattern: string, path: string = ''): Promise<{ success: boolean; matches?: string[] }> {
  try {
    const res = await fetch(`${API_BASE}/fs/search`, {
      method: 'POST',
      headers: apiHeaders(),
      body: JSON.stringify({ pattern, path }),
    });
    return res.json();
  } catch (e) {
    return { success: false, matches: [] };
  }
}

export async function putFileContent(path: string, content: string): Promise<{ success: boolean; detail?: string }> {
  const res = await fetch(`${API_BASE}/fs/file/content`, {
    method: 'PUT',
    headers: apiHeaders(),
    body: JSON.stringify({ path, content }),
  });
  return res.json();
}
