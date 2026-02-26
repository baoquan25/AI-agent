import logging

from daytona import Daytona, DaytonaConfig
from langchain_openai import ChatOpenAI
from langchain.agents import create_agent

from config import OPENAI_API_KEY, DAYTONA_API_KEY, DAYTONA_API_URL
from tools import get_tools

logger = logging.getLogger("llm")

LABEL_KEY = "app-user-id"

SYSTEM_PROMPT = (
    "Bạn là một coder chuyên nghiệp. "
    "Bạn có thể đọc file, liệt kê file, ghi file và chạy lệnh trong sandbox. "
    "Workspace của user nằm tại đường dẫn SDK 'workspace/' (tương đương /home/daytona/workspace). "
    "Sử dụng tối ưu nhất các tool để hoàn thành công việc."
)

def get_daytona() :
    config = DaytonaConfig(
        api_key=DAYTONA_API_KEY, 
        api_url=DAYTONA_API_URL
        )
    return Daytona(config)

def find_sandbox(user_id: str):
    daytona = get_daytona()
    try:
        sandbox = daytona.find_one(labels={LABEL_KEY: user_id})
        logger.info(f"Found sandbox for user {user_id}: {sandbox.id}")
        return sandbox
    except Exception as e:
        logger.warning(f"No sandbox found for user {user_id}: {e}")
        return None

def get_agent(sandbox):
    llm = ChatOpenAI(
        model="gpt-5-nano",
        api_key=OPENAI_API_KEY,
    )
    tools = get_tools(sandbox)
    agent = create_agent(model=llm, tools=tools, system_prompt=SYSTEM_PROMPT)
    return agent


async def llm_answer(user_input: str, user_id: str = "default_user") -> str:
    sandbox = find_sandbox(user_id)
    if sandbox is None:
        return "Không tìm thấy sandbox cho user. Vui lòng mở workspace trước."

    agent = get_agent(sandbox)
    result = await agent.ainvoke({"messages": [("human", user_input)]})
    messages = result.get("messages", [])
    if messages:
        return messages[-1].content
    return "No response from agent."

async def llm_answer(user_input: str, user_id: str = "default_user") -> str:
    sandbox = find_sandbox(user_id)
    if sandbox is None:
        return "Không tìm thấy sandbox cho user. Vui lòng mở workspace trước."

    agent = get_agent(sandbox)
    result = await agent.ainvoke({"messages": [("human", user_input)]})
    messages = result.get("messages", [])
    if messages:
        return messages[-1].content
    return "No response from agent."