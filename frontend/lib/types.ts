export interface TreeNode {
  type: 'file' | 'directory';
  name: string;
  path?: string;
  children?: TreeNode[];
  size?: number;
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
