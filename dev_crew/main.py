import argparse

from dotenv import load_dotenv

from .crew import build_crew


def main() -> None:
    load_dotenv()

    parser = argparse.ArgumentParser(
        description="Have a CrewAI crew (Backend, Frontend, QA) build a feature in the "
        "wodify-clone app by delegating real work to Claude Code."
    )
    parser.add_argument(
        "--feature",
        required=True,
        help="A self-contained description of the feature to build, e.g. "
        "'Add a GET /api/v1/health endpoint that returns {\"status\": \"ok\"}'",
    )
    args = parser.parse_args()

    crew = build_crew(args.feature)
    result = crew.kickoff()
    print(result)


if __name__ == "__main__":
    main()
