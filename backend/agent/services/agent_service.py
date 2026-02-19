# pyright: basic
# type: ignore

"""
AgentService — creates LLM, Agent, Conversation, and extracts reply.

Extracted from routers/agent.py to keep the router thin.
"""

import os
import logging

from pydantic import SecretStr

from openhands.sdk import LLM, Agent, Conversation, Event, LLMConvertibleEvent, Tool
from openhands.tools.task_tracker import TaskTrackerTool

from config import settings
from tools.registry import create_tools

logger = logging.getLogger("daytona-api")


class AgentService:
    """Orchestrates agent chat: tools, LLM, conversation, reply extraction."""

    def run_chat(self, sandbox, user_id: str, message: str, sandbox_workspace: str) -> dict:
        execution_log: list[dict] = []

        # Register Daytona tools for this sandbox
        toolset_name = create_tools(sandbox, execution_log=execution_log)

        # Local workspace for OpenHands internal state (not user files)
        local_workspace = os.path.join("/tmp", "openhands_workspaces", user_id.replace(os.sep, "_"))
        os.makedirs(local_workspace, exist_ok=True)

        llm = LLM(
            usage_id="agent",
            model=settings.LLM_MODEL,
            api_key=SecretStr(settings.OPENAI_KEY),
        )

        agent = Agent(
            llm=llm,
            tools=[
                Tool(name=toolset_name),
                Tool(name=TaskTrackerTool.name),
            ],
        )

        # Capture agent messages
        llm_messages = []

        def conversation_callback(event: Event):
            if isinstance(event, LLMConvertibleEvent):
                llm_messages.append(event.to_llm_message())

        conversation = Conversation(
            agent=agent,
            callbacks=[conversation_callback],
            workspace=local_workspace,
        )

        full_message = (
            f"[Sandbox workspace: {sandbox_workspace}]\n"
            f"Use AgentToolSet to operate on files/code inside the sandbox at the path above.\n\n"
            f"{message}"
        )
        conversation.send_message(full_message)
        conversation.run()

        agent_reply = self._extract_reply(llm_messages)
        return {"agent_reply": agent_reply, "code_outputs": execution_log}

    @staticmethod
    def _extract_reply(llm_messages: list) -> str:
        """Extract the last assistant text from captured LLM messages."""
        for msg in reversed(llm_messages):
            role = getattr(msg, "role", None)
            if role != "assistant":
                continue

            content = getattr(msg, "content", None)
            if not content:
                continue

            if isinstance(content, str) and content.strip():
                return content.strip()

            if isinstance(content, list):
                texts = []
                for part in content:
                    text = getattr(part, "text", None)
                    if text is None and isinstance(part, dict):
                        text = part.get("text", "")
                    if text:
                        texts.append(str(text))
                if texts:
                    return "\n".join(texts)

        return "Agent completed the task but produced no text reply."
