"""
session/llm.py — Sandbox + graph (agent↔tool) + stream text.
Conversation dùng LangGraph checkpointer (thread_id), không lưu history thủ công.
"""

from __future__ import annotations

import logging
import operator
from collections.abc import AsyncGenerator
from typing import Literal

from langchain_core.messages import AnyMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_openai import ChatOpenAI
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph
from typing_extensions import Annotated, TypedDict

from .config import DAYTONA_API_KEY, DAYTONA_API_URL, OPENAI_API_KEY
from tool.tools import get_tools

logger = logging.getLogger("session.llm")

LABEL_KEY = "app-user-id"


_checkpointer = MemorySaver()

SYSTEM_PROMPT = (
    "Bạn là coder trong Daytona sandbox. "
    "Dùng tool: đọc/ghi file, liệt kê thư mục, chạy lệnh. "
    "Workspace: 'workspace/' (= /home/daytona/workspace). "
    "Phân tích → chọn tool → thực hiện → trả lời."
)


class MessagesState(TypedDict):
    messages: Annotated[list[AnyMessage], operator.add]
    llm_calls: int


def _get_sandbox(user_id: str):
    from daytona import Daytona, DaytonaConfig

    daytona = Daytona(DaytonaConfig(api_key=DAYTONA_API_KEY, api_url=DAYTONA_API_URL))
    try:
        return daytona.find_one(labels={LABEL_KEY: user_id})
    except Exception as e:
        logger.warning("No sandbox for user %s: %s", user_id, e)
        return None


def get_agent(sandbox):
    """Build LangGraph với checkpointer: state được lưu theo thread_id."""
    llm = ChatOpenAI(model="gpt-4o-mini", api_key=OPENAI_API_KEY)
    tools = get_tools(sandbox)
    tools_by_name = {t.name: t for t in tools}
    model_with_tools = llm.bind_tools(tools)

    def agent_node(state: MessagesState):
        messages = [SystemMessage(content=SYSTEM_PROMPT)] + state["messages"]
        response = model_with_tools.invoke(messages)
        return {"messages": [response], "llm_calls": state.get("llm_calls", 0) + 1}

    def tool_node(state: dict):
        result = []
        for tool_call in state["messages"][-1].tool_calls:
            tool = tools_by_name[tool_call["name"]]
            observation = tool.invoke(tool_call["args"])
            result.append(ToolMessage(content=str(observation), tool_call_id=tool_call["id"]))
        return {"messages": result}

    def should_continue(state: MessagesState) -> Literal["tool_node", "__end__"]:
        last = state["messages"][-1]
        return "tool_node" if last.tool_calls else END

    graph = StateGraph(MessagesState)
    graph.add_node("agent", agent_node)
    graph.add_node("tool_node", tool_node)
    graph.add_edge(START, "agent")
    graph.add_conditional_edges("agent", should_continue, ["tool_node", END])
    graph.add_edge("tool_node", "agent")
    return graph.compile(checkpointer=_checkpointer)


async def llm_answer(user_input: str, user_id: str = "default_user") -> AsyncGenerator[str, None]:
    """Stream text từ LLM. Dùng thread_id = user_id để checkpointer có key bắt buộc."""
    sandbox = _get_sandbox(user_id)
    if sandbox is None:
        return
    agent = get_agent(sandbox)
    config = {"configurable": {"thread_id": user_id}}
    async for chunk, _ in agent.astream(
        {"messages": [HumanMessage(content=user_input)], "llm_calls": 0},
        config=config,
        stream_mode="messages",
    ):
        if hasattr(chunk, "content") and chunk.content:
            yield chunk.content


async def llm_answer_with_thread(
    user_input: str,
    user_id: str = "default_user",
    thread_id: str = "",
) -> AsyncGenerator[str, None]:
    """Stream text với phiên LangGraph (thread_id). Checkpointer tự lưu/load lịch sử."""
    if not thread_id:
        return
    sandbox = _get_sandbox(user_id)
    if sandbox is None:
        return
    agent = get_agent(sandbox)
    config = {"configurable": {"thread_id": thread_id}}
    async for chunk, _ in agent.astream(
        {"messages": [HumanMessage(content=user_input)], "llm_calls": 0},
        config=config,
        stream_mode="messages",
    ):
        if hasattr(chunk, "content") and chunk.content:
            yield chunk.content


def get_thread_messages(thread_id: str, user_id: str) -> list[dict]:
    """Lấy lịch sử messages của thread (từ checkpointer). Trả về [{"role": "user"|"assistant", "content": str}, ...]."""
    sandbox = _get_sandbox(user_id)
    if sandbox is None:
        return []
    agent = get_agent(sandbox)
    config = {"configurable": {"thread_id": thread_id}}
    state = agent.get_state(config)
    if not state or not state.values.get("messages"):
        return []
    out = []
    for m in state.values["messages"]:
        role = "user" if isinstance(m, HumanMessage) else "assistant"
        content = getattr(m, "content", "")
        if isinstance(content, list):
            content = content[0].get("text", "") if content else ""
        content = str(content or "")
        out.append({"role": role, "content": content})
    return out
