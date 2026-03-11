'use client';

type HeaderProps = {
  leftBarVisible: boolean;
  onToggleLeftBar: () => void;
  outputPanelVisible: boolean;
  onToggleOutputPanel: () => void;
  agentPanelVisible: boolean;
  onToggleAgentPanel: () => void;
};

export function Header({
  leftBarVisible,
  onToggleLeftBar,
  outputPanelVisible,
  onToggleOutputPanel,
  agentPanelVisible,
  onToggleAgentPanel,
}: HeaderProps) {
  return (
    <header>
      <span className="brand">Cursor</span>
      <div className="header-actions">
        <button
          type="button"
          className={`header-btn ${leftBarVisible ? 'active' : ''}`}
          onClick={onToggleLeftBar}
          title="Bật/tắt Left Bar (Files)"
          aria-label="Bật/tắt Left Bar"
        >
          <span className="codicon codicon-layout-sidebar-left" />
        </button>
        <button
          type="button"
          className={`header-btn ${outputPanelVisible ? 'active' : ''}`}
          onClick={onToggleOutputPanel}
          title="Bật/tắt panel Output / Terminal"
          aria-label="Bật/tắt panel Output"
        >
          <span className="codicon codicon-layout-panel" />
        </button>
        <button
          type="button"
          className={`header-btn ${agentPanelVisible ? 'active' : ''}`}
          onClick={onToggleAgentPanel}
          title="Bật/tắt panel Chat (Agent)"
          aria-label="Bật/tắt panel Chat"
        >
          <span className="codicon codicon-layout-sidebar-right" />
        </button>
      </div>
    </header>
  );
}
