---
name: finance
triggers: ["đầu tư", "tài chính", "phân bổ tài sản", "chứng khoán", "cổ phiếu", "trái phiếu", "vàng", "bất động sản", "BĐS", "quỹ ETF", "tiết kiệm", "lợi nhuận", "rủi ro đầu tư", "danh mục đầu tư", "investment", "portfolio", "stock", "bond", "finance"]
---

When the user asks about personal investment, asset allocation, financial planning, or wealth management, delegate to the `investment_advisor` subagent.

## Workflow

1. Spawn the subagent:
   - id: `finance`
   - agent_types: `["investment_advisor"]`

2. Delegate the user's question as-is to the `finance` subagent.

3. Return the subagent's response directly to the user.

## Example delegation

User asks: *"Tôi có 500 triệu, nên đầu tư vào đâu?"*

→ Spawn: `{"command": "spawn", "ids": ["finance"], "agent_types": ["investment_advisor"]}`

→ Delegate: `{"command": "delegate", "tasks": {"finance": "Tôi có 500 triệu, nên đầu tư vào đâu?"}}`

## Important

- Always pass `agent_types: ["investment_advisor"]` when spawning — do not omit it.
- Do not answer finance questions yourself; delegate to the specialist subagent.
