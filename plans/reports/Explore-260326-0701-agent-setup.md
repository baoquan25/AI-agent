# Daytona Backend Agent Setup Analysis

## Overview
The Daytona backend uses the **OpenHands SDK** to create a conversational AI agent that can execute tools in a sandbox environment. The agent runs on a FastAPI server (port 8001) and communicates with a Daytona sandbox instance.

## Key Files

### Core Agent Execution
- **`/home/ducminh/daytona/backend/agent/services/llm.py`** — Main agent runner
- **`/home/ducminh/daytona/backend/agent/routers/thread_router.py`** — API endpoints for conversations
- **`/home/ducminh/daytona/backend/agent/services/conversation.py`** — Thread/conversation state management
- **`/home/ducminh/daytona/backend/agent/config.py`** — Settings/environment
- **`/home/ducminh/daytona/backend/agent/services/agent_context.py`** — Agent context & plugins
- **`/home/ducminh/daytona/backend/agent/dependencies.py`** — Daytona sandbox client
- **`/home/ducminh/daytona/backend/agent/tools/registry.py`** — Tool registration

### Tool Definitions
- **`/home/ducminh/daytona/backend/agent/tools/editor/definition.py`** — FileEditorTool
- **`/home/ducminh/daytona/backend/agent/tools/terminal/definition.py`** — TerminalTool
- **`/home/ducminh/daytona/backend/agent/tools/run/definition.py`** — RunFileTool
- **`/home/ducminh/daytona/backend/agent/tools/apply_patch/definition.py`** — ApplyPatchTool
- **`/home/ducminh/daytona/backend/agent/tools/grep/definition.py`** — GrepTool
- **`/home/ducminh/daytona/backend/agent/tools/glob/definition.py`** — GlobTool
- **`/home/ducminh/daytona/backend/agent/tools/browser_use/definition.py`** — BrowserToolSet

---

## 1. Agent Initialization Flow (`run_agent` Function)

**Location:** `/home/ducminh/daytona/backend/agent/services/llm.py:80-115`

```python
def run_agent(sandbox, sandbox_id: str, message: str, conversation_id: str | None = None,
              token_queue: asyncio.Queue | None = None, loop: asyncio.AbstractEventLoop | None = None,
              execution_log: list | None = None, file_edits: list | None = None) -> str:
```

### Key Steps:
1. **Register all tools** (line 17 in llm.py):
   ```python
   register_all_tools()
   ```

2. **Create local workspace** for agent:
   ```python
   local_workspace = os.path.join("/tmp", "openhands_workspaces", sandbox_id.replace(os.sep, "_"))
   os.makedirs(local_workspace, exist_ok=True)
   ```

3. **Initialize Agent** with LLM + tools (lines 19-37):
   ```python
   def _create_agent(tools):
       request_llm = LLM(
           usage_id="agent",
           model=settings.LLM_MODEL,           # From env (e.g., "gpt-4o")
           api_key=settings.OPENAI_KEY,
           reasoning_effort=settings.REASONING_EFFORT,  # e.g., "high"
           stream=True,
       )
       request_condenser = LLMSummarizingCondenser(...)
       return Agent(
           llm=request_llm,
           tools=tools,                        # Tool references
           agent_context=agent_context,        # Includes skills from plugins
           condenser=request_condenser,        # Summarizes long conversations
       )
   ```

4. **Create Conversation** with hooks and state (lines 97-104):
   ```python
   conversation = Conversation(
       agent=agent,
       token_callbacks=token_callbacks,        # For streaming tokens
       workspace=local_workspace,
       persistence_dir=PERSISTENCE_DIR,
       conversation_id=resolved_id,
       hook_config=plugin.hooks,              # Post-tool-use hooks
   )
   ```

5. **Inject sandbox into conversation state** (lines 107-109):
   ```python
   conversation._state.agent_state["sandbox"] = sandbox
   conversation._state.agent_state["execution_log"] = execution_log if execution_log is not None else []
   conversation._state.agent_state["file_edits"] = file_edits if file_edits is not None else []
   ```

6. **Send message and run agent**:
   ```python
   conversation.send_message(message)
   conversation.run()
   ```

---

## 2. LLM Configuration

**Location:** `/home/ducminh/daytona/backend/agent/services/llm.py:19-37`

### OpenAI LLM Setup:
```python
request_llm = LLM(
    usage_id="agent",                    # Tracking ID
    model=settings.LLM_MODEL,            # e.g., "gpt-4o"
    api_key=settings.OPENAI_KEY,         # From OpenAI
    reasoning_effort=settings.REASONING_EFFORT,  # "low" | "medium" | "high"
    stream=True,                         # Enable token streaming
)
```

### Context Condenser:
```python
request_condenser = LLMSummarizingCondenser(
    llm=request_llm.model_copy(update={"usage_id": "condenser"}),
    max_size=24,                        # Max messages before summarization
    keep_first=2,                       # Keep system + first msg
)
```

### Settings:
**Location:** `/home/ducminh/daytona/backend/agent/config.py`

```python
class Settings(BaseSettings):
    LLM_MODEL: str              # e.g., "gpt-4o" or "gpt-4-turbo"
    REASONING_EFFORT: str       # "low" | "medium" | "high"
    OPENAI_KEY: str             # OpenAI API key
    
    SANDBOX_API_URL: str        # Sandbox service URL
    DAYTONA_API_URL: str        # Daytona API URL
    DAYTONA_API_KEY: str        # Daytona auth key
    # ... other fields
```

---

## 3. Tool Registration

**Location:** `/home/ducminh/daytona/backend/agent/tools/registry.py`

### Registration Function:
```python
def register_all_tools():
    global _REGISTERED
    if _REGISTERED:
        return
    register_tool("FileEditorTool", FileEditorTool)
    register_tool("RunFileTool", RunFileTool)
    register_tool("TerminalTool", TerminalTool)
    register_tool("ApplyPatchTool", ApplyPatchTool)
    register_tool("GrepTool", GrepTool)
    register_tool("GlobTool", GlobTool)
    register_tool("BrowserToolSet", BrowserToolSet)
    _REGISTERED = True
```

### Get Tool References for Agent:
```python
def get_tool_references():
    return [
        Tool(name="FileEditorTool"),
        Tool(name="RunFileTool"),
        Tool(name="TerminalTool"),
        Tool(name="ApplyPatchTool"),
        Tool(name="GrepTool"),
        Tool(name="GlobTool"),
        Tool(name="BrowserToolSet"),
    ]
```

---

## 4. Tool Definition Architecture

All tools follow this pattern:

### 1. Action Class (Input)
```python
class MyToolAction(Action):
    param1: str = Field(description="...")
    param2: int = Field(default=10, ge=0, le=100)
```

### 2. Observation Class (Output)
```python
class MyToolObservation(Observation):
    result: str = ""
    success: bool = True
    
    @property
    def to_llm_content(self) -> Sequence[TextContent | ImageContent]:
        # Format output for LLM consumption
        return [TextContent(text=self.result)]
```

### 3. Executor Class (Implementation)
```python
class MyToolExecutor(ToolExecutor[MyToolAction, MyToolObservation]):
    def __init__(self, sandbox: Sandbox):
        self.sandbox = sandbox
    
    def __call__(self, action: MyToolAction, conversation=None) -> MyToolObservation:
        # Execute tool logic
        return MyToolObservation(result=..., success=True)
```

### 4. Tool Definition Class (Registration)
```python
class MyTool(ToolDefinition[MyToolAction, MyToolObservation]):
    @classmethod
    def create(cls, conv_state, *, sandbox: Sandbox | None = None) -> Sequence[ToolDefinition]:
        if sandbox is None:
            sandbox = conv_state.agent_state.get("sandbox")
        if not sandbox:
            raise ValueError("sandbox not found in conv_state.agent_state")
        
        executor = MyToolExecutor(sandbox)
        return [cls(
            description="Tool description for LLM",
            action_type=MyToolAction,
            observation_type=MyToolObservation,
            executor=executor,
        )]
```

---

## 5. Existing Custom Tools

### FileEditorTool
- **Purpose:** View/create/edit files with str_replace operations
- **Actions:** `view`, `create`, `str_replace`, `insert`, `undo_edit`
- **State Tracking:** None (stateless)

### TerminalTool
- **Purpose:** Execute bash commands in persistent shell
- **Actions:** Single command execution with working directory tracking
- **State Tracking:** Tracks working directory & environment variables
- **File:** `/home/ducminh/daytona/backend/agent/tools/terminal/impl.py`

### RunFileTool
- **Purpose:** Run existing files via sandbox /run API (like UI run button)
- **Actions:** Execute & get Jupyter-rich output
- **State Tracking:** Maintains `execution_log` (passed from agent state)

### ApplyPatchTool
- **Purpose:** Multi-file edits with unified patch format
- **Actions:** `*** Begin Patch` ... `*** End Patch` format
- **State Tracking:** Maintains `file_edits` list (passed from agent state)

### GrepTool
- **Purpose:** Search file contents with regex
- **Actions:** Pattern search, case sensitivity, context lines
- **Annotations:** `readOnlyHint=True`, `destructiveHint=False`

### GlobTool
- **Purpose:** Fast file pattern matching
- **Actions:** Glob pattern search
- **Annotations:** `readOnlyHint=True`, `destructiveHint=False`

### BrowserToolSet
- **Purpose:** Web automation (complex, multipart tool set)
- **State Tracking:** Maintains browser session & screenshots

---

## 6. Agent Context & Plugins

**Location:** `/home/ducminh/daytona/backend/agent/services/agent_context.py`

```python
plugin = Plugin.load(_plugins_dir)  # Load from /backend/agent/plugins/

agent_context = AgentContext(
    skills=plugin.get_all_skills(),  # Loads from plugins/skills/*.md
)
```

### Plugin Structure:
```
/backend/agent/plugins/
├── .plugin/plugin.json          # Plugin metadata
├── hooks/hooks.json             # PostToolUse hooks (echo messages)
├── .mcp.json                    # MCP config
└── skills/                       # Markdown skill definitions
    ├── navigation.md
    ├── security.md
    ├── code_review.md
    ├── debugging.md
    ├── test.md
    └── ...
```

### PostToolUse Hooks:
Tools like `file_editor`, `apply_patch`, `terminal` trigger hooks that run shell commands after tool execution (currently just echo statements).

---

## 7. Agent State Management

**Location:** `/home/ducminh/daytona/backend/agent/services/conversation.py`

```python
_threads: dict[str, dict] = {}  # In-memory thread store

def create_thread(thread_id: str, metadata: dict) -> dict:
    return {
        "thread_id": thread_id,
        "created_at": "...",
        "updated_at": "...",
        "metadata": metadata,          # Client metadata (user_id, api_key)
        "status": "idle",
        "values": {"messages": []},    # Conversation messages
    }
```

### Thread Structure:
- `values.messages`: List of `{"type": "human"|"ai", "content": "...", "id": "msg-..."}`
- `values.code_outputs`: Execution log (populated by RunFileTool)
- `values.file_edits`: File changes (populated by ApplyPatchTool & FileEditorTool)

---

## 8. Streaming & Real-time Updates

**Location:** `/home/ducminh/daytona/backend/agent/routers/thread_router.py:132-232`

### Streaming Response:
```python
@router.post("/threads/{thread_id}/runs/stream")
async def run_stream(thread_id: str, request: Request):
    async def event_stream():
        # Server-Sent Events (SSE) format
        yield sse("metadata", {"run_id": "..."})
        
        # Run agent in executor (non-blocking)
        loop.run_in_executor(None, _run)
        
        # Stream tokens as they arrive
        while True:
            item = await token_queue.get()
            if item is _SENTINEL:
                break
            if item.get("type") == "content":
                yield sse("messages", [...])
        
        # Final state
        yield sse("values", thread["values"])
        yield "event: end\ndata: \"\"\n\n"
    
    return StreamingResponse(event_stream(), media_type="text/event-stream")
```

### Token Callback:
```python
def make_token_callback(queue: asyncio.Queue, loop, content_parts):
    def on_token(chunk: ModelResponseStream):
        for choice in chunk.choices:
            delta = choice.delta
            # Stream thinking, content, tool_name, tool_args
            if reasoning_content:
                loop.call_soon_threadsafe(queue.put_nowait, {"type": "thinking", ...})
            if content:
                loop.call_soon_threadsafe(queue.put_nowait, {"type": "content", ...})
            if tool_calls:
                loop.call_soon_threadsafe(queue.put_nowait, {"type": "tool_name", ...})
    return on_token
```

---

## 9. Sandbox Integration

**Location:** `/home/ducminh/daytona/backend/agent/dependencies.py`

```python
from daytona import Daytona, DaytonaConfig

daytona = Daytona(DaytonaConfig(
    api_key=settings.DAYTONA_API_KEY,
    api_url=settings.DAYTONA_API_URL,
))

def get_sandbox(sandbox_id: str):
    sandbox = daytona.get(sandbox_id)
    if sandbox.state == SandboxState.STARTED:
        return sandbox
    if sandbox.state in (SandboxState.STOPPED, SandboxState.STOPPING):
        daytona.start(sandbox)
        return sandbox
    return None
```

### Sandbox Object Methods:
- `sandbox.fs.download_file(path)` — Read file bytes
- `sandbox.fs.upload_file(bytes, path)` — Write file
- `sandbox.fs.create_folder(path, mode)` — Create directory
- `sandbox.fs.delete_file(path)` — Delete file
- `sandbox.process.exec(cmd, timeout)` — Run shell command

---

## 10. How Tools Access Sandbox

### Pattern 1: Direct Injection
```python
class MyTool(ToolDefinition[MyAction, MyObservation]):
    @classmethod
    def create(cls, conv_state, *, sandbox: Sandbox | None = None):
        if sandbox is None:
            sandbox = conv_state.agent_state.get("sandbox")
        executor = MyExecutor(sandbox)
        return [cls(..., executor=executor)]
```

### Pattern 2: Shared State
```python
class MyTool(ToolDefinition[MyAction, MyObservation]):
    @classmethod
    def create(cls, conv_state, *, sandbox: Sandbox | None = None, 
               file_edits: list | None = None):
        if file_edits is None:
            file_edits = conv_state.agent_state.get("file_edits")
        executor = MyExecutor(sandbox, file_edits=file_edits)
        return [cls(..., executor=executor)]
```

### Where State is Set:
**Location:** `/home/ducminh/daytona/backend/agent/services/llm.py:107-109`

```python
conversation._state.agent_state["sandbox"] = sandbox
conversation._state.agent_state["execution_log"] = execution_log or []
conversation._state.agent_state["file_edits"] = file_edits or []
```

---

## 11. Tool Annotations

Optional metadata for the LLM:

```python
from openhands.sdk.tool import ToolAnnotations

ToolAnnotations(
    title="grep",                    # Display name
    readOnlyHint=True,              # Doesn't modify files
    destructiveHint=False,          # Not permanent (can undo)
    idempotentHint=True,            # Same result each call
    openWorldHint=False,            # Deterministic/no external effects
)
```

---

## Summary: Building a Custom Delegate Tool

To create a delegate tool that manages sub-agents or task delegation:

1. **Define Action & Observation:**
   ```python
   class DelegateAction(Action):
       task: str = Field(description="Task to delegate")
       agent_type: str = Field(default="agent", description="Type of agent")
   
   class DelegateObservation(Observation):
       result: str = ""
       success: bool = True
   ```

2. **Implement Executor:**
   ```python
   class DelegateExecutor(ToolExecutor[DelegateAction, DelegateObservation]):
       def __init__(self, sandbox: Sandbox):
           self.sandbox = sandbox
       
       def __call__(self, action: DelegateAction, conversation=None) -> DelegateObservation:
           # Create sub-agent, run task, return result
           ...
   ```

3. **Create Tool Definition:**
   ```python
   class DelegateTool(ToolDefinition[DelegateAction, DelegateObservation]):
       @classmethod
       def create(cls, conv_state, *, sandbox: Sandbox | None = None):
           if sandbox is None:
               sandbox = conv_state.agent_state.get("sandbox")
           executor = DelegateExecutor(sandbox)
           return [cls(
               description="Delegate tasks to sub-agents",
               action_type=DelegateAction,
               observation_type=DelegateObservation,
               executor=executor,
           )]
   ```

4. **Register in Registry:**
   ```python
   # tools/registry.py
   from tools.delegate.definition import DelegateTool
   
   register_tool("DelegateTool", DelegateTool)
   # Add to get_tool_references()
   ```

5. **Access Conversation State if Needed:**
   ```python
   def __call__(self, action, conversation=None) -> DelegateObservation:
       if conversation:
           # Access conversation._state.agent_state for shared state
           sandbox = conversation._state.agent_state.get("sandbox")
   ```

---

## Key Design Patterns

1. **Tool Creation is Lazy:** Tools are created when agent runs, not at registration
2. **Executor Holds Dependencies:** Sandbox, shared state lists are passed to executor
3. **Observation Formatting:** `to_llm_content` controls what LLM sees
4. **Error Handling:** Executors catch exceptions and return failed observations
5. **State Sharing:** Lists like `file_edits`, `execution_log` are passed by reference
6. **Streaming:** Tokens streamed via asyncio.Queue for real-time updates
7. **Plugin Hooks:** PostToolUse hooks can trigger after tool execution
