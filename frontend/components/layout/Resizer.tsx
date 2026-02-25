'use client';

type ResizerKind = 'file' | 'chat' | 'editor';

type ResizerProps = {
  kind: ResizerKind;
  resizing: string | null;
  onMouseDown: (e: React.MouseEvent) => void;
  title?: string;
};

export function Resizer({ kind, resizing, onMouseDown, title }: ResizerProps) {
  const isVertical = kind === 'file' || kind === 'chat';
  const className = isVertical ? `resizer-v ${resizing === kind ? 'resizing' : ''}` : `resizer-h ${resizing === kind ? 'resizing' : ''}`;
  return <div className={className} onMouseDown={onMouseDown} title={title ?? 'Kéo để đổi kích thước'} />;
}
