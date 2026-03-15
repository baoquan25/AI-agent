---
name: test-and-verify
triggers: ["kiểm tra", "xác minh", "chạy kiểm tra", "kiểm thử", "kiểm tra đơn vị", "kiểm tra tích hợp", "chạy thử"]
---

Use this skill when writing code, fixing bugs, changing behavior, or finishing a task that should be verified.

Goal:
Verify the change with the narrowest useful checks first.

Workflow:
1. Confirm syntax or import sanity.
2. Run the changed file or the smallest relevant command first.
3. Run the most targeted tests for the affected area.
4. Expand verification only if needed.
5. Report:
   - what was run
   - whether it passed or failed
   - any limitations

Rules:
- Do not say "done" without verification details.
- Prefer targeted tests before broad suites.
- If verification could not be completed, say exactly why.
- Do not hide failing output.

Verification order:
1. Syntax / import sanity
2. Focused execution
3. Targeted tests
4. Broader suite if needed