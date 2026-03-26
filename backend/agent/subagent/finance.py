from openhands.tools.delegate.registration import register_agent
from openhands.sdk import LLM, Agent, AgentContext
from openhands.sdk.context import Skill


def create_investment_advisor(llm: LLM) -> Agent:
   
    skills = [
        Skill(
            name="investment_planning",
            content=(
                "Bạn là chuyên gia đầu tư cơ bản cho nhà đầu tư cá nhân. "
                "Hãy đánh giá mục tiêu tài chính ngắn hạn và trung hạn, "
                "mức chịu rủi ro, và đề xuất phân bổ tài sản đơn giản như "
                "tiền mặt, tiền gửi, trái phiếu, quỹ ETF, hoặc cổ phiếu blue-chip. "
                "Ưu tiên phương án an toàn, dễ hiểu, không hứa hẹn lợi nhuận phi thực tế. "
                "Trả lời súc tích, rõ ràng, theo từng bước."
            ),
            triggers=["đầu tư", "tài chính", "phân bổ tài sản", "chứng khoán", "cổ phiếu"],
        )
    ]
    return Agent(
        llm=llm,
        tools=[],
        agent_context=AgentContext(
            skills=skills,
            system_message_suffix=(
                "Chỉ tập trung vào định hướng đầu tư cơ bản và phân bổ tài sản "
                "vào chứng khoán, BĐS, vàng, trái phiếu, quỹ mở."
            ),
        ),
    )


register_agent(
    name="investment_advisor",
    factory_func=create_investment_advisor,
    description=(
        "Đưa ra định hướng đầu tư cơ bản và phân bổ tài sản cho cá nhân: "
        "chứng khoán, vàng, BĐS."
    ),
)
