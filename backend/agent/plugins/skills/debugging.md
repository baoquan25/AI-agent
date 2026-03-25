---
name: debugging
triggers: ["gỡ lỗi", "sửa lỗi", "lỗi", "ngoại lệ", "vết lỗi", "dấu vết lỗi", "test lỗi", "chạy lỗi", "không hoạt động"]
---

Use this skill for runtime errors, stack traces, exceptions, failing tests, incorrect behavior, and bug investigation.

Goal:
Find the root cause before making a fix.

Workflow:
1. Reproduce the issue.
2. Narrow the scope to the smallest failing component.
3. Read the stack trace, logs, and surrounding code first.
4. Form 1–3 concrete hypotheses.
5. Validate each hypothesis with targeted inspection or execution.
6. Apply the smallest safe fix.
7. Re-run the relevant file or test.
8. Summarize:
   - root cause
   - fix
   - what was verified

Rules:
- Do not make broad speculative changes.
- Prefer evidence over guesswork.
- If the issue is not reproducible, say so clearly and explain what was checked.
- Fix the cause, not only the symptom.

Debugging checklist:
- What failed?
- Where did it fail?
- Can it be reproduced consistently?
- What recent or local assumptions are invalid?
- What is the smallest safe fix?