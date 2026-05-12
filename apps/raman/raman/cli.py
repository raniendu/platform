from __future__ import annotations

import argparse
from collections.abc import Sequence


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="raman")
    parser.add_argument(
        "--agent",
        default=None,
        help="Agent name to load from spec/ (default: raman)",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> None:
    args = build_parser().parse_args(argv)

    from raman.agent import build_agent
    from raman.settings import RamanSettings
    from raman.spec import load_spec

    settings = RamanSettings()
    if args.agent:
        settings = settings.model_copy(update={"default_agent": args.agent})
    spec = load_spec(settings.default_agent, settings.spec_root)
    build_agent(spec=spec, settings=settings).to_cli_sync(prog_name=spec.name)


if __name__ == "__main__":
    main()
