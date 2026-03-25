import os
import uuid
import asyncio
from typing import Literal
from openhands.sdk import LLM, Agent, Conversation, get_logger
from openhands.sdk.context.condenser import LLMSummarizingCondenser
from openhands.sdk.llm.streaming import ModelResponseStream

from config import settings
from tools.registry import register_all_tools, get_tool_references
from services.agent_context import agent_context, plugin

logger = get_logger(__name__)
PERSISTENCE_DIR = "/tmp/openhands-conversations"
StreamingState = Literal["thinking", "content", "tool_name", "tool_args"]

register_all_tools()

def _create_agent(tools):
    request_llm = LLM(
        usage_id="agent",
        model=settings.LLM_MODEL,
        api_key=settings.OPENAI_KEY,
        reasoning_effort=settings.REASONING_EFFORT,
        stream=True,
    )
    request_condenser = LLMSummarizingCondenser(
        llm=request_llm.model_copy(update={"usage_id": "condenser"}),
        max_size=24,
        keep_first=2,
    )
    return Agent(
        llm=request_llm,
        tools=tools,
        agent_context=agent_context,
        condenser=request_condenser,
    )


def make_token_callback(queue: asyncio.Queue, loop: asyncio.AbstractEventLoop, content_parts: list[str]):

    _current_state: StreamingState | None = None

    def on_token(chunk: ModelResponseStream) -> None:
        nonlocal _current_state

        for choice in chunk.choices:
            delta = choice.delta
            if delta is None:
                continue

            reasoning_content = getattr(delta, "reasoning_content", None)
            if isinstance(reasoning_content, str) and reasoning_content:
                if _current_state != "thinking":
                    _current_state = "thinking"
                loop.call_soon_threadsafe(queue.put_nowait, {"type": "thinking", "content": reasoning_content})

            content = getattr(delta, "content", None)
            if isinstance(content, str) and content:
                if _current_state != "content":
                    _current_state = "content"
                content_parts.append(content)
                loop.call_soon_threadsafe(queue.put_nowait, {"type": "content", "content": content})

            tool_calls = getattr(delta, "tool_calls", None)
            if tool_calls:
                for tool_call in tool_calls:
                    name = tool_call.function.name if tool_call.function.name else ""
                    args = tool_call.function.arguments if tool_call.function.arguments else ""
                    if name:
                        _current_state = "tool_name"
                        loop.call_soon_threadsafe(queue.put_nowait, {"type": "tool_name", "content": name})
                    if args:
                        _current_state = "tool_args"
                        loop.call_soon_threadsafe(queue.put_nowait, {"type": "tool_args", "content": args})

    return on_token


def run_agent(sandbox, sandbox_id: str, message: str, conversation_id: str | None = None,
              token_queue: asyncio.Queue | None = None, loop: asyncio.AbstractEventLoop | None = None,
              execution_log: list | None = None, file_edits: list | None = None) -> str:
    tools = get_tool_references()

    local_workspace = os.path.join("/tmp", "openhands_workspaces", sandbox_id.replace(os.sep, "_"))
    os.makedirs(local_workspace, exist_ok=True)

    agent = _create_agent(tools)

    resolved_id = uuid.UUID(conversation_id) if conversation_id else uuid.uuid4()

    content_parts: list[str] = []
    token_callbacks = []
    if token_queue is not None and loop is not None:
        token_callbacks.append(make_token_callback(token_queue, loop, content_parts))

    conversation = Conversation(
        agent=agent,
        token_callbacks=token_callbacks,
        workspace=local_workspace,
        persistence_dir=PERSISTENCE_DIR,
        conversation_id=resolved_id,
        hook_config=plugin.hooks,
    )


    conversation._state.agent_state["sandbox"] = sandbox
    conversation._state.agent_state["execution_log"] = execution_log if execution_log is not None else []
    conversation._state.agent_state["file_edits"] = file_edits if file_edits is not None else []


    conversation.send_message(message)
    conversation.run()

    return "".join(content_parts)
