> ## Documentation Index
> Fetch the complete documentation index at: https://docs.openhands.dev/llms.txt
> Use this file to discover all available pages before exploring further.

# LLM Streaming

> Stream LLM responses token-by-token for real-time display and interactive user experiences.

export const path_to_script_0 = "examples/01_standalone_sdk/29_llm_streaming.py"

<Warning>
  This is currently only supported for the chat completion endpoint.
</Warning>

> A ready-to-run example is available [here](#ready-to-run-example)!

Enable real-time display of LLM responses as they're generated, token by token. This guide demonstrates how to use
streaming callbacks to process and display tokens as they arrive from the language model.

## How It Works

Streaming allows you to display LLM responses progressively as the model generates them, rather than waiting for the
complete response. This creates a more responsive user experience, especially for long-form content generation.

<Steps>
  <Step>
    ### Enable Streaming on LLM

    Configure the LLM with streaming enabled:

    ```python focus={6} icon="python" wrap theme={null}
    llm = LLM(
        model="anthropic/claude-sonnet-4-5-20250929",
        api_key=SecretStr(api_key),
        base_url=base_url,
        usage_id="stream-demo",
        stream=True,  # Enable streaming
    )
    ```
  </Step>

  <Step>
    ### Define Token Callback

    Create a callback function that processes streaming chunks as they arrive:

    ```python icon="python" wrap theme={null}
    def on_token(chunk: ModelResponseStream) -> None:
        """Process each streaming chunk as it arrives."""
        choices = chunk.choices
        for choice in choices:
            delta = choice.delta
            if delta is not None:
                content = getattr(delta, "content", None)
                if isinstance(content, str):
                    sys.stdout.write(content)
                    sys.stdout.flush()
    ```

    The callback receives a `ModelResponseStream` object containing:

    * **`choices`**: List of response choices from the model
    * **`delta`**: Incremental content changes for each choice
    * **`content`**: The actual text tokens being streamed
  </Step>

  <Step>
    ### Register Callback with Conversation

    Pass your token callback to the conversation:

    ```python focus={3} icon="python" wrap theme={null}
    conversation = Conversation(
        agent=agent,
        token_callbacks=[on_token],  # Register streaming callback
        workspace=os.getcwd(),
    )
    ```

    The `token_callbacks` parameter accepts a list of callbacks, allowing you to register multiple handlers
    if needed (e.g., one for display, another for logging).
  </Step>
</Steps>

## Ready-to-run Example

<Note>
  This example is available on GitHub: [examples/01\_standalone\_sdk/29\_llm\_streaming.py](https://github.com/OpenHands/software-agent-sdk/blob/main/examples/01_standalone_sdk/29_llm_streaming.py)
</Note>

```python icon="python" expandable examples/01_standalone_sdk/29_llm_streaming.py theme={null}
import os
import sys
from typing import Literal

from pydantic import SecretStr

from openhands.sdk import (
    Conversation,
    get_logger,
)
from openhands.sdk.llm import LLM
from openhands.sdk.llm.streaming import ModelResponseStream
from openhands.tools.preset.default import get_default_agent


logger = get_logger(__name__)


api_key = os.getenv("LLM_API_KEY") or os.getenv("OPENAI_API_KEY")
if not api_key:
    raise RuntimeError("Set LLM_API_KEY or OPENAI_API_KEY in your environment.")

model = os.getenv("LLM_MODEL", "anthropic/claude-sonnet-4-5-20250929")
base_url = os.getenv("LLM_BASE_URL")
llm = LLM(
    model=model,
    api_key=SecretStr(api_key),
    base_url=base_url,
    usage_id="stream-demo",
    stream=True,
)

agent = get_default_agent(llm=llm, cli_mode=True)


# Define streaming states
StreamingState = Literal["thinking", "content", "tool_name", "tool_args"]
# Track state across on_token calls for boundary detection
_current_state: StreamingState | None = None


def on_token(chunk: ModelResponseStream) -> None:
    """
    Handle all types of streaming tokens including content,
    tool calls, and thinking blocks with dynamic boundary detection.
    """
    global _current_state

    choices = chunk.choices
    for choice in choices:
        delta = choice.delta
        if delta is not None:
            # Handle thinking blocks (reasoning content)
            reasoning_content = getattr(delta, "reasoning_content", None)
            if isinstance(reasoning_content, str) and reasoning_content:
                if _current_state != "thinking":
                    if _current_state is not None:
                        sys.stdout.write("\n")
                    sys.stdout.write("THINKING: ")
                    _current_state = "thinking"
                sys.stdout.write(reasoning_content)
                sys.stdout.flush()

            # Handle regular content
            content = getattr(delta, "content", None)
            if isinstance(content, str) and content:
                if _current_state != "content":
                    if _current_state is not None:
                        sys.stdout.write("\n")
                    sys.stdout.write("CONTENT: ")
                    _current_state = "content"
                sys.stdout.write(content)
                sys.stdout.flush()

            # Handle tool calls
            tool_calls = getattr(delta, "tool_calls", None)
            if tool_calls:
                for tool_call in tool_calls:
                    tool_name = (
                        tool_call.function.name if tool_call.function.name else ""
                    )
                    tool_args = (
                        tool_call.function.arguments
                        if tool_call.function.arguments
                        else ""
                    )
                    if tool_name:
                        if _current_state != "tool_name":
                            if _current_state is not None:
                                sys.stdout.write("\n")
                            sys.stdout.write("TOOL NAME: ")
                            _current_state = "tool_name"
                        sys.stdout.write(tool_name)
                        sys.stdout.flush()
                    if tool_args:
                        if _current_state != "tool_args":
                            if _current_state is not None:
                                sys.stdout.write("\n")
                            sys.stdout.write("TOOL ARGS: ")
                            _current_state = "tool_args"
                        sys.stdout.write(tool_args)
                        sys.stdout.flush()


conversation = Conversation(
    agent=agent,
    workspace=os.getcwd(),
    token_callbacks=[on_token],
)

story_prompt = (
    "Tell me a long story about LLM streaming, write it a file, "
    "make sure it has multiple paragraphs. "
)
conversation.send_message(story_prompt)
print("Token Streaming:")
print("-" * 100 + "\n")
conversation.run()

cleanup_prompt = (
    "Thank you. Please delete the streaming story file now that I've read it, "
    "then confirm the deletion."
)
conversation.send_message(cleanup_prompt)
print("Token Streaming:")
print("-" * 100 + "\n")
conversation.run()

# Report cost
cost = llm.metrics.accumulated_cost
print(f"EXAMPLE_COST: {cost}")
```

You can run the example code as-is.

<Note>
  The model name should follow the [LiteLLM convention](https://models.litellm.ai/): `provider/model_name` (e.g., `anthropic/claude-sonnet-4-5-20250929`, `openai/gpt-4o`).
  The `LLM_API_KEY` should be the API key for your chosen provider.
</Note>

<CodeGroup>
  <CodeBlock language="bash" filename="Bring-your-own provider key" icon="terminal" wrap>
    {`export LLM_API_KEY="your-api-key"\nexport LLM_MODEL="anthropic/claude-sonnet-4-5-20250929"  # or openai/gpt-4o, etc.\ncd software-agent-sdk\nuv run python ${path_to_script_0}`}
  </CodeBlock>

  <CodeBlock language="bash" filename="OpenHands Cloud" icon="terminal" wrap>
    {`# https://app.all-hands.dev/settings/api-keys\nexport LLM_API_KEY="your-openhands-api-key"\nexport LLM_MODEL="openhands/claude-sonnet-4-5-20250929"\ncd software-agent-sdk\nuv run python ${path_to_script_0}`}
  </CodeBlock>
</CodeGroup>

<Tip>
  **ChatGPT Plus/Pro subscribers**: You can use `LLM.subscription_login()` to authenticate with your ChatGPT account and access Codex models without consuming API credits. See the [LLM Subscriptions guide](/sdk/guides/llm-subscriptions) for details.
</Tip>

## Next Steps

* **[LLM Error Handling](/sdk/guides/llm-error-handling)** - Handle streaming errors gracefully
* **[Custom Visualizer](/sdk/guides/convo-custom-visualizer)** - Build custom UI for streaming
* **[Interactive Terminal](/sdk/guides/agent-interactive-terminal)** - Display streams in terminal UI
