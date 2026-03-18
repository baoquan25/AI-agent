---
name: navigation
triggers: ["mã nguồn", "kiến trúc", "cấu trúc dự án", "tìm file", "tìm chỗ xử lý", "điểm bắt đầu", "luồng chạy", "xem repo"]
---

Use this skill when exploring an unfamiliar repository, locating entrypoints, tracing behavior, or mapping relevant files and modules.

Goal:
Locate the smallest set of relevant files before changing code.

Workflow:
1. Identify entrypoints and configuration files first.
2. Trace imports and call flow from the user-facing behavior to the implementation.
3. Find similar existing patterns and follow them.
4. Prefer source-of-truth files over generated or derived files.
5. Record which files are responsible for:
   - input handling
   - business logic
   - persistence
   - output rendering

Rules:
- Avoid changing generated files unless the task explicitly requires it.
- Prefer existing conventions over introducing new structure.
- Do not make edits until the relevant code path is understood.

Output:
When helpful, summarize:
- key entrypoints
- main modules involved
- the smallest safe set of files to change