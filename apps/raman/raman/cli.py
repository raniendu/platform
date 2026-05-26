from __future__ import annotations

import argparse
import json
import sys
from collections.abc import AsyncIterator, Sequence
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from pydantic_ai import Agent
    from pydantic_ai.messages import ModelMessage
    from rich.console import Console

CODE_THEME = "monokai"
HISTORY_PATH = Path.home() / ".raman" / "cli_history"


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
    parser.add_argument(
        "-q",
        "--quiet",
        action="store_true",
        help=(
            "Hide thinking and tool-call events in interactive chat; only "
            "stream the final reply."
        ),
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
    if args.quiet and args.once:
        parser.error("--quiet cannot be combined with --once")

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

    import asyncio

    asyncio.run(run_interactive(agent, prog_name=spec.name, quiet=args.quiet))


async def run_interactive(agent: "Agent", *, prog_name: str, quiet: bool) -> None:
    from prompt_toolkit import PromptSession
    from prompt_toolkit.history import FileHistory
    from pydantic_ai._cli import CustomAutoSuggest, handle_slash_command
    from rich.console import Console

    HISTORY_PATH.parent.mkdir(parents=True, exist_ok=True)
    HISTORY_PATH.touch(exist_ok=True)

    session: PromptSession[Any] = PromptSession(history=FileHistory(str(HISTORY_PATH)))
    console = Console()
    messages: list[ModelMessage] = []
    multiline = False
    auto_suggest = CustomAutoSuggest(["/markdown", "/multiline", "/exit", "/cp"])

    while True:
        try:
            text = await session.prompt_async(
                f"{prog_name} ➤ ", auto_suggest=auto_suggest, multiline=multiline
            )
        except (KeyboardInterrupt, EOFError):
            console.print("[dim]Exiting…[/dim]")
            return

        if not text.strip():
            continue

        ident_prompt = text.lower().strip().replace(" ", "-")
        if ident_prompt.startswith("/"):
            exit_value, multiline = handle_slash_command(
                ident_prompt, messages, multiline, console, CODE_THEME
            )
            if exit_value is not None:
                return
            continue

        try:
            messages = await _render_turn(agent, text, messages, console, quiet=quiet)
        except KeyboardInterrupt:
            console.print("[dim]Interrupted[/dim]")
        except Exception as exc:  # pragma: no cover - surface anything else to user
            console.print(f"\n[red]{type(exc).__name__}[/red]: {exc}")


async def _render_turn(
    agent: "Agent",
    prompt: str,
    messages: list["ModelMessage"],
    console: "Console",
    *,
    quiet: bool,
) -> list["ModelMessage"]:
    from pydantic_ai import Agent as _Agent

    tool_timers: dict[str, float] = {}

    async with agent.iter(prompt, message_history=messages) as agent_run:
        async for node in agent_run:
            if _Agent.is_model_request_node(node):
                async with node.stream(agent_run.ctx) as stream:
                    await _render_model_request(stream, console, quiet=quiet)
            elif _Agent.is_call_tools_node(node):
                async with node.stream(agent_run.ctx) as stream:
                    await _render_call_tools(
                        stream, console, quiet=quiet, tool_timers=tool_timers
                    )
        assert agent_run.result is not None
        return list(agent_run.result.all_messages())


async def _render_model_request(
    stream: AsyncIterator[Any], console: "Console", *, quiet: bool
) -> None:
    from pydantic_ai.messages import (
        PartDeltaEvent,
        PartEndEvent,
        PartStartEvent,
        TextPartDelta,
        ThinkingPartDelta,
    )
    from rich.live import Live
    from rich.markdown import Markdown
    from rich.text import Text

    buffers: dict[int, str] = {}
    kinds: dict[int, str] = {}
    text_live: Live | None = None
    text_live_index: int | None = None

    def _stop_text_live() -> None:
        nonlocal text_live, text_live_index
        if text_live is not None:
            text_live.stop()
            text_live = None
            text_live_index = None

    def _flush_thinking(idx: int) -> None:
        body = buffers.get(idx, "").strip()
        if not body:
            return
        console.print("[dim]· thinking:[/dim]")
        for line in body.splitlines():
            console.print(f"  [dim]{line}[/dim]")
        console.print()

    try:
        async for event in stream:
            if isinstance(event, PartStartEvent):
                idx = event.index
                kind = event.part.part_kind
                kinds[idx] = kind
                initial = getattr(event.part, "content", "") or ""
                buffers[idx] = initial if isinstance(initial, str) else ""

                if kind == "text":
                    _stop_text_live()
                    renderable = (
                        Markdown(buffers[idx], code_theme=CODE_THEME)
                        if buffers[idx]
                        else Text("")
                    )
                    text_live = Live(
                        renderable,
                        refresh_per_second=15,
                        console=console,
                        vertical_overflow="visible",
                    )
                    text_live.start()
                    text_live_index = idx

            elif isinstance(event, PartDeltaEvent):
                idx = event.index
                if isinstance(event.delta, TextPartDelta):
                    buffers[idx] = buffers.get(idx, "") + (
                        event.delta.content_delta or ""
                    )
                    if text_live is not None and text_live_index == idx:
                        text_live.update(Markdown(buffers[idx], code_theme=CODE_THEME))
                elif isinstance(event.delta, ThinkingPartDelta):
                    buffers[idx] = buffers.get(idx, "") + (
                        event.delta.content_delta or ""
                    )

            elif isinstance(event, PartEndEvent):
                idx = event.index
                kind = kinds.get(idx)
                if kind == "thinking" and not quiet:
                    _flush_thinking(idx)
                    buffers[idx] = ""
                elif kind == "text" and text_live_index == idx:
                    _stop_text_live()
    finally:
        _stop_text_live()
        # Some streams may not emit PartEndEvent for thinking parts; flush remaining.
        if not quiet:
            for idx, kind in kinds.items():
                if kind == "thinking" and buffers.get(idx):
                    _flush_thinking(idx)
                    buffers[idx] = ""


async def _render_call_tools(
    stream: AsyncIterator[Any],
    console: "Console",
    *,
    quiet: bool,
    tool_timers: dict[str, float],
) -> None:
    import time

    from pydantic_ai.messages import (
        FunctionToolCallEvent,
        FunctionToolResultEvent,
    )

    async for event in stream:
        if isinstance(event, FunctionToolCallEvent):
            tool_timers[event.tool_call_id] = time.monotonic()
            if quiet:
                continue
            part = event.part
            args_repr = _format_call_args(part)
            console.print(f"[cyan]→ {part.tool_name}({args_repr})[/cyan]")
        elif isinstance(event, FunctionToolResultEvent):
            start = tool_timers.pop(event.tool_call_id, None)
            duration = time.monotonic() - start if start is not None else None
            if quiet:
                continue
            part = event.part
            duration_str = (
                f" [dim]{duration:.1f}s[/dim]" if duration is not None else ""
            )
            if part.part_kind == "retry-prompt":
                console.print(f"[red]✗ {part.tool_name or '?'}[/red]{duration_str}")
                body = _stringify_retry_content(part.content)
            else:
                console.print(f"[green]✓ {part.tool_name}[/green]{duration_str}")
                body = _stringify_tool_return(part)
            if body:
                for line in body.splitlines():
                    console.print(f"  [dim]{line}[/dim]")
            console.print()


def _format_call_args(part: Any) -> str:
    try:
        args = part.args_as_dict()
    except Exception:
        return _truncate(str(getattr(part, "args", "")) or "")
    if not args:
        return ""
    return ", ".join(f"{k}={_repr_value(v)}" for k, v in args.items())


def _repr_value(value: Any) -> str:
    if isinstance(value, str):
        return json.dumps(value)
    try:
        return json.dumps(value, default=str)
    except Exception:
        return repr(value)


def _stringify_tool_return(part: Any) -> str:
    try:
        items = part.content_items(mode="str")
    except Exception:
        return str(part.content)
    rendered: list[str] = []
    for item in items:
        if isinstance(item, str):
            rendered.append(item)
        else:
            rendered.append(f"<{type(item).__name__}>")
    return "\n".join(rendered)


def _stringify_retry_content(content: Any) -> str:
    if isinstance(content, str):
        return content
    try:
        return json.dumps(content, default=str, indent=2)
    except Exception:
        return str(content)


def _truncate(text: str, limit: int = 200) -> str:
    if len(text) <= limit:
        return text
    return text[: limit - 1] + "…"


if __name__ == "__main__":
    main()
