from __future__ import annotations

import argparse
import asyncio
from collections.abc import Sequence


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="vikram")
    parser.add_argument(
        "--agent",
        default=None,
        help="Agent name to load from spec/ (default: vikram)",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> None:
    args = build_parser().parse_args(argv)

    from vikram.agent import build_agent_runner
    from vikram.settings import VikramSettings
    from vikram.spec import load_spec

    settings = VikramSettings()
    if args.agent:
        settings = settings.model_copy(update={"default_agent": args.agent})
    spec = load_spec(settings.default_agent, settings.spec_root)
    runner = build_agent_runner(spec=spec, settings=settings)
    history: bytes | None = None
    while True:
        try:
            prompt = input(f"{spec.name}> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return
        if not prompt:
            continue
        if prompt in {"/exit", "/quit"}:
            return
        result = asyncio.run(
            runner.run(
                prompt,
                message_history_json=history,
                conversation_id=f"cli:{spec.name}",
            )
        )
        history = result.message_history_json
        print(result.output)


if __name__ == "__main__":
    main()
