from pathlib import Path

from openhands.sdk import AgentContext
from openhands.sdk.context import Skill

_agent_dir = Path(__file__).resolve().parent.parent
_skills_dir = _agent_dir / "skills"

_skill_files = [
    "debugging.md",
    "navigation.md",
    "security.md",
    "test.md",
]
_skills = [Skill.load(_skills_dir / f) for f in _skill_files]

agent_context = AgentContext(
    skills=_skills,
    load_public_skills=True,
)
