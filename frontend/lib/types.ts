export interface TreeNode {
  type: 'file' | 'directory';
  name: string;
  path?: string;
  children?: TreeNode[];
}

export interface TabItem {
  path: string;
  name: string;
}

export interface FileCacheItem {
  content: string;
  modified: boolean;
}

export interface ChatMessage {
  sender: 'user' | 'ai';
  text: string;
  icon?: 'error' | 'success';
  isThinking?: boolean;
}

export interface FileEdit {
  path: string;
  action: 'create' | 'update' | 'delete';
  old_content: string | null;
  new_content: string | null;
}
