'use client';

import { VscLayoutSidebarLeft, VscLayoutPanel, VscLayoutSidebarRight } from '../../lib/icons';

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
          <VscLayoutSidebarLeft size={14} />
        </button>
        <button
          type="button"
          className={`header-btn ${outputPanelVisible ? 'active' : ''}`}
          onClick={onToggleOutputPanel}
          title="Bật/tắt panel Output / Terminal"
          aria-label="Bật/tắt panel Output"
        >
          <VscLayoutPanel size={14} />
        </button>
        <button
          type="button"
          className={`header-btn ${agentPanelVisible ? 'active' : ''}`}
          onClick={onToggleAgentPanel}
          title="Bật/tắt panel Chat (Agent)"
          aria-label="Bật/tắt panel Chat"
        >
          <VscLayoutSidebarRight size={14} />
        </button>
      </div>
    </header>
  );
}
