import json
import os
import subprocess

from crewai.tools import tool

DEFAULT_TIMEOUT_SECONDS = 900
MAX_RESULT_CHARS = 6000

# These are needed for CrewAI's own agent LLM calls, but if left in the
# environment they leak into the `claude` subprocess and make Claude Code try
# to authenticate via API key instead of the user's existing claude.ai login,
# which it refuses to do ("connectors are disabled because ANTHROPIC_API_KEY
# ... takes precedence over your claude.ai login"). Strip them so the
# sub-invocation uses the same login as running `claude` by hand would.
_ENV_VARS_TO_STRIP = ("ANTHROPIC_API_KEY", "OPENAI_API_KEY", "CREWAI_LLM_MODEL")

# Claude Code in `-p` mode tends to summarize its work ("shown above", "all
# files printed above") rather than transcribing content into its final
# reply. That's fine in an interactive terminal where the asker can see the
# transcript, but the caller here only ever receives this function's return
# value — never the sub-session's intermediate tool output. Appending this
# reminder to every prompt fixes that structurally, regardless of how the
# calling agent happens to phrase its request.
_TRANSCRIPT_REMINDER = (
    "\n\nIMPORTANT: I (the requester) cannot see any of your intermediate tool "
    "calls or their output — only the final text you reply with. If I asked you "
    "to show file contents, command output, or any other text, you MUST include "
    "that text verbatim in your final reply. Do not say things like 'shown above' "
    "or 'printed above' — there is no 'above' from my perspective."
)


def _wodify_clone_dir() -> str:
    configured = os.getenv("WODIFY_CLONE_DIR", "../web")
    return os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", configured))


def _subprocess_env() -> dict:
    return {k: v for k, v in os.environ.items() if k not in _ENV_VARS_TO_STRIP}


@tool("Run Claude Code")
def run_claude_code(prompt: str, max_turns: int = 20) -> str:
    """Delegate a real coding task to Claude Code, running headlessly inside the
    wodify-clone app's working directory. `prompt` should be a complete,
    self-contained instruction (persona, task, and any context from prior
    agents) — Claude Code has no memory of this crew's conversation, only what
    is in `prompt` and the repository itself. Returns Claude Code's final
    result text, or an error message starting with "ERROR:" if the
    invocation failed (non-zero exit, timeout, or malformed output) — in
    which case do not treat the task as done."""
    cwd = _wodify_clone_dir()
    if not os.path.isdir(cwd):
        return f"ERROR: WODIFY_CLONE_DIR does not exist: {cwd}"

    try:
        completed = subprocess.run(
            [
                "claude",
                "-p",
                prompt + _TRANSCRIPT_REMINDER,
                "--permission-mode",
                "bypassPermissions",
                "--output-format",
                "json",
                "--max-turns",
                str(max_turns),
            ],
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=DEFAULT_TIMEOUT_SECONDS,
            env=_subprocess_env(),
        )
    except subprocess.TimeoutExpired:
        return f"ERROR: claude -p timed out after {DEFAULT_TIMEOUT_SECONDS}s"
    except FileNotFoundError:
        return "ERROR: `claude` CLI not found on PATH — is Claude Code installed?"

    if completed.returncode != 0:
        return f"ERROR: claude -p exited {completed.returncode}: {completed.stderr.strip() or completed.stdout.strip()}"

    try:
        data = json.loads(completed.stdout)
    except json.JSONDecodeError:
        return f"ERROR: could not parse Claude Code JSON output: {completed.stdout[:2000]}"

    if data.get("is_error"):
        return f"ERROR: Claude Code reported an error: {data.get('result', data)}"

    result_text = str(data.get("result", ""))
    if not result_text:
        return "ERROR: Claude Code returned no result text"

    # A single huge result (e.g. several full files dumped verbatim) can blow
    # out the calling CrewAI agent's context badly enough to make its next
    # tool call malformed. Cap it — if the agent needs more, it can ask a
    # narrower follow-up question.
    if len(result_text) > MAX_RESULT_CHARS:
        result_text = (
            result_text[:MAX_RESULT_CHARS]
            + f"\n\n[truncated — {len(result_text)} chars total; ask a narrower follow-up if you need more]"
        )
    return result_text
