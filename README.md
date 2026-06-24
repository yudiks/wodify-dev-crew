# Dev Crew — CrewAI orchestrating Claude Code

A CrewAI crew of three personas — **Backend Engineer**, **Frontend Engineer**, **QA
Automation Engineer** — that build features in the [`web/`](../web) wodify-clone app.
Each agent's only tool delegates the actual coding work to **Claude Code**, run
headlessly as a subprocess (`claude -p ...`) inside `web/`.

This is a separate project from [`src/wodify_summarizer/`](../src/wodify_summarizer)
(which summarizes Wodify gym data) — same CrewAI conventions, different purpose.

## How it works

1. `dev_crew.crew.build_crew(feature_description)` builds a sequential `Crew`:
   Backend → Frontend → QA, each a CrewAI `Task` whose `context` includes the prior
   task's output (CrewAI's standard handoff mechanism).
2. Each agent's CrewAI-side LLM (your `OPENAI_API_KEY`/`ANTHROPIC_API_KEY`) decides
   *what* to ask for; it never touches the filesystem directly. Its one tool,
   `run_claude_code` (`dev_crew/tools/claude_code_tool.py`), shells out to:
   ```
   claude -p "<prompt>" --permission-mode bypassPermissions --output-format json --max-turns 20
   ```
   with `cwd` set to `WODIFY_CLONE_DIR` (defaults to `../web`). That's a *second*,
   independent Claude Code session that actually reads/edits files and runs shell
   commands — using your existing local Claude Code login, not a new credential.
3. The tool returns Claude Code's final result text, which becomes the CrewAI
   task's output and flows into the next agent's context.

## ⚠️ Safety note

Sub-agent invocations run with `--permission-mode bypassPermissions` — **no
permission prompts at all**, by design (there's no human present in a headless
loop to answer them). That's only reasonable because this targets your own local
dev sandbox (`web/`), not shared or production infrastructure. Don't point
`WODIFY_CLONE_DIR` at anything you're not comfortable having edited and executed
against autonomously.

## Setup

```bash
cd agents
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # set OPENAI_API_KEY or ANTHROPIC_API_KEY
```

Requires the `claude` CLI already installed and logged in (`claude` should work
from your shell before running this).

## Usage

```bash
python -m dev_crew.main --feature "Add a GET /api/v1/health endpoint that returns {\"status\": \"ok\"}, with a Vitest test for it"
```

Each agent's output (and Claude Code's underlying work) is printed as it runs
(`verbose=True`); the final printed result is the QA agent's pass/fail report.

## Extending

- Give agents richer/narrower instructions by editing the `backstory`/`goal`
  strings and the `REPO_CONVENTIONS` block in `dev_crew/crew.py` — that block is
  what keeps every Claude Code sub-invocation pointed at this repo's actual
  conventions instead of generic boilerplate.
- To add a fourth persona (e.g. a code reviewer), add another `Agent` + `Task`
  with `context=[...]` pointing at whichever prior tasks it needs.
- To make agents run truly in parallel instead of sequential handoff, you'd need
  per-agent git worktrees (so concurrent Claude Code processes don't clobber each
  other's file edits) plus a merge/integration step — not implemented here.
