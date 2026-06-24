import os

from crewai import Agent, Crew, Process, Task

from .tools import ALL_TOOLS

# Model for the CrewAI agents' own reasoning loop (separate from Claude Code,
# which is invoked by the Run Claude Code tool using its own login). Override
# via the CREWAI_LLM_MODEL env var if needed.
AGENT_LLM = os.getenv("CREWAI_LLM_MODEL", "anthropic/claude-sonnet-4-6")

REPO_CONVENTIONS = (
    "This is a Next.js 16 App Router + TypeScript app (in the current working "
    "directory). API routes live under app/api/v1/<resource>/route.ts (list+search "
    "GET, POST) and app/api/v1/<resource>/[id]/route.ts (GET/PUT/DELETE), built on "
    "shared helpers in lib/crud.ts, lib/http.ts, and lib/query.ts (Wodify's "
    "q=field|operator|value search syntax) — reuse these instead of writing new "
    "boilerplate. Prisma schema is prisma/schema.prisma; the Prisma client singleton "
    "is lib/db.ts. The admin UI is components/Dashboard.tsx + ResourceManager.tsx, "
    "configured per-resource in lib/resource-configs.ts. The Member Portal is "
    "components/ClientPortal.tsx under app/portal/. Tests are Vitest files under "
    "tests/, calling route handlers directly (see tests/helpers.ts for the "
    "makeRequest/ctx pattern). Always run `npm test` and `npm run build` before "
    "reporting a task done, and fix any failures yourself."
)


def _delegate_task(persona_instruction: str, work_instruction: str) -> str:
    """Builds a single self-contained prompt for the `run_claude_code` tool, since
    Claude Code has no memory of this crew's conversation — only what's in the
    prompt and the repository itself."""
    return f"{persona_instruction}\n\n{REPO_CONVENTIONS}\n\nYour task:\n{work_instruction}"


def build_crew(feature_description: str) -> Crew:
    backend_engineer = Agent(
        role="Backend Engineer",
        goal=(
            f"Implement the API, schema, and data-layer changes needed for: {feature_description}"
        ),
        backstory=(
            "You are a backend engineer for the wodify-clone app. You design and "
            "implement Next.js route handlers and Prisma schema changes, following "
            "the existing conventions in this repo exactly rather than inventing new "
            "patterns. You delegate the actual file edits and commands to the "
            "Run Claude Code tool, since that's the only thing that can touch the "
            "repository."
        ),
        tools=ALL_TOOLS,
        llm=AGENT_LLM,
        verbose=True,
    )

    frontend_engineer = Agent(
        role="Frontend Engineer",
        goal=f"Build or update the UI needed for: {feature_description}",
        backstory=(
            "You are a frontend engineer for the wodify-clone app. You build React "
            "UI in the admin dashboard or member portal that consumes whatever API "
            "the Backend Engineer built, following existing component patterns. If "
            "a feature genuinely needs no UI change, say so plainly instead of "
            "inventing busywork. You delegate all actual file edits to the "
            "Run Claude Code tool."
        ),
        tools=ALL_TOOLS,
        llm=AGENT_LLM,
        verbose=True,
    )

    qa_engineer = Agent(
        role="QA Automation Engineer",
        goal=f"Verify, with automated tests, that the following works end-to-end: {feature_description}",
        backstory=(
            "You are a QA automation engineer for the wodify-clone app. You write "
            "or extend Vitest tests covering the new behavior, then actually run "
            "`npm test` and `npm run build` and report the real pass/fail result — "
            "never claim success without having run them. You delegate all actual "
            "file edits and command execution to the Run Claude Code tool."
        ),
        tools=ALL_TOOLS,
        llm=AGENT_LLM,
        verbose=True,
    )

    backend_task = Task(
        description=_delegate_task(
            "You are acting as the Backend Engineer.",
            f"Implement the backend (API routes / Prisma schema+migration as needed) for: "
            f"{feature_description}. Use the Run Claude Code tool to make the actual changes "
            f"in the repository, then run `npm test` and `npm run build` yourself via that "
            f"tool to confirm nothing broke.",
        ),
        expected_output=(
            "A summary of the backend changes made (files touched, new endpoints/fields), "
            "and confirmation that tests and the build passed."
        ),
        agent=backend_engineer,
    )

    frontend_task = Task(
        description=_delegate_task(
            "You are acting as the Frontend Engineer.",
            f"Given the backend work already completed (see context), build or update the UI "
            f"for: {feature_description}. Use the Run Claude Code tool to make the actual "
            f"changes. If no UI change is genuinely needed, state that instead of making one "
            f"up.",
        ),
        expected_output=(
            "A summary of the UI changes made (or an explicit statement that none were "
            "needed), and confirmation that the build still passes."
        ),
        agent=frontend_engineer,
        context=[backend_task],
    )

    qa_task = Task(
        description=_delegate_task(
            "You are acting as the QA Automation Engineer.",
            f"Given the backend and frontend work already completed (see context), write or "
            f"extend automated tests covering: {feature_description}. Use the Run Claude Code "
            f"tool to add the tests and actually run `npm test` and `npm run build`. Report "
            f"the real results — do not claim success without having run them.",
        ),
        expected_output="The actual test/build output (pass or fail) and a summary of test coverage added.",
        agent=qa_engineer,
        context=[backend_task, frontend_task],
    )

    return Crew(
        agents=[backend_engineer, frontend_engineer, qa_engineer],
        tasks=[backend_task, frontend_task, qa_task],
        process=Process.sequential,
        verbose=True,
    )
