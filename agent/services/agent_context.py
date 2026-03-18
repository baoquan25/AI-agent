from pathlib import Path

from openhands.sdk import AgentContext
from openhands.sdk.plugin import Plugin

_agent_dir = Path(__file__).resolve().parent.parent
_plugins_dir = _agent_dir / "plugins"

plugin = Plugin.load(_plugins_dir)

agent_context = AgentContext(
    skills=plugin.get_all_skills(),
)
