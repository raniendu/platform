from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from pathlib import Path


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="raman")
    parser.add_argument(
        "--agent",
        default=None,
        help="Agent name to load from spec/ (default: raman)",
    )
    parser.add_argument(
        "--once",
        action="store_true",
        help="Run one prompt and exit instead of starting interactive chat.",
    )
    parser.add_argument(
        "--prompt",
        default=None,
        help=(
            "Prompt text, '-' for stdin, '@path' for a prompt file, or an "
            "existing file path."
        ),
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit one-shot output as JSON.",
    )
    return parser


def read_prompt(value: str) -> str:
    if value == "-":
        return sys.stdin.read()

    if value.startswith("@") and len(value) > 1:
        return Path(value[1:]).expanduser().read_text(encoding="utf-8")

    path = Path(value).expanduser()
    if path.is_file():
        return path.read_text(encoding="utf-8")

    return value


def main(argv: Sequence[str] | None = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.prompt is not None and not args.once:
        parser.error("--prompt requires --once")
    if args.json and not args.once:
        parser.error("--json requires --once")
    if args.once and args.prompt is None:
        parser.error("--once requires --prompt")

    from raman.agent import build_agent
    from raman.settings import RamanSettings
    from raman.spec import load_spec

    settings = RamanSettings()
    if args.agent:
        settings = settings.model_copy(update={"default_agent": args.agent})
    spec = load_spec(settings.default_agent, settings.spec_root)
    agent = build_agent(spec=spec, settings=settings)

    if args.once:
        result = agent.run_sync(read_prompt(args.prompt))
        output = str(result.output)
        if args.json:
            print(json.dumps({"agent": spec.name, "output": output}))
        else:
            print(output)
        return

    agent.to_cli_sync(prog_name=spec.name)


if __name__ == "__main__":
    main()
