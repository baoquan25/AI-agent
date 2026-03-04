'use client';

type TreeInlineCreateProps = {
  level: number;
  mode: 'file' | 'folder';
  value: string;
  onChange: (value: string) => void;
  onBlur: () => void;
  onKeyDown: (e: React.KeyboardEvent) => void;
  inputRef: React.RefObject<HTMLInputElement | null>;
};

export function TreeInlineCreate({ level, mode, value, onChange, onBlur, onKeyDown, inputRef }: TreeInlineCreateProps) {
  return (
    <div className="tree-item tree-inline-create-row" style={{ paddingLeft: 8 + level * 8 }}>
      <div className="tree-item-content">
        <span className={`tree-lead-icon codicon codicon-${mode === 'file' ? 'list-flat' : 'chevron-right'}`} style={{ pointerEvents: 'none' }} />
        <input
          ref={inputRef as React.RefObject<HTMLInputElement>}
          type="text"
          className="tree-inline-input"
          placeholder={mode === 'file' ? 'File name' : 'Folder name'}
          value={value}
          onChange={(e) => onChange(e.target.value)}
          onBlur={onBlur}
          onKeyDown={onKeyDown}
        />
      </div>
    </div>
  );
}
