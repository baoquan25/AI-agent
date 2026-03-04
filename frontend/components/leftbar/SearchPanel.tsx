'use client';

type SearchPanelProps = {
  searchPattern: string;
  onSearchPatternChange: (value: string) => void;
  searchResults: string[];
  searchInputRef: React.RefObject<HTMLInputElement | null>;
  chatLoading: boolean;
  openTabs: { path: string }[];
  onResultClick: (path: string) => void;
  switchTab: (path: string) => void;
};

export function SearchPanel({
  searchPattern,
  onSearchPatternChange,
  searchResults,
  searchInputRef,
  chatLoading,
  openTabs,
  onResultClick,
  switchTab,
}: SearchPanelProps) {
  return (
    <div className="leftbar-search-panel">
      <div className="leftbar-search-header">Search</div>
      <div className="leftbar-search-row">
        <input
          ref={searchInputRef as React.RefObject<HTMLInputElement>}
          type="text"
          className="leftbar-search-input"
          value={searchPattern}
          onChange={(e) => onSearchPatternChange(e.target.value)}
          placeholder="Search"
        />
      </div>
      <div className="leftbar-search-results">
        {searchResults.length === 0 ? (
          <div className="leftbar-search-empty">No files found</div>
        ) : (
          searchResults.map((match) => (
            <div
              key={match}
              className="leftbar-search-item"
              onClick={() => {
                if (chatLoading) {
                  if (openTabs.some((t) => t.path === match)) switchTab(match);
                  return;
                }
                onResultClick(match);
              }}
            >
              <span
                className={`codicon ${match.toLowerCase().endsWith('.py') ? 'codicon-python' : 'codicon-file'}`}
                style={{ marginRight: 6, fontSize: 12 }}
              />
              {match}
            </div>
          ))
        )}
      </div>
    </div>
  );
}
