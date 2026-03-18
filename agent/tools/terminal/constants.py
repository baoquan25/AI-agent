# pyright: basic
# type: ignore

"""Constants for the terminal tool."""

MAX_OUTPUT_CHARS: int = 80_000

DEFAULT_TIMEOUT: int = 30

DEFAULT_CWD: str = "/workspace"

CWD_SENTINEL: str = "__CWD__"

TIMEOUT_MESSAGE: str = (
    "You may retry with a higher `timeout` value, "
    "or run the command in the background: `command > output.log 2>&1 &`"
)
