from __future__ import annotations

import asyncio

from vikram.agent import build_agent_runner
from vikram.settings import VikramSettings
from vikram.spec import load_spec


async def main() -> None:
    settings = VikramSettings()
    spec = load_spec(settings.default_agent, settings.spec_root)
    runner = build_agent_runner(spec=spec, settings=settings)
    for prompt in ("What is your name?", "What is today's date?"):
        result = await runner.run(
            prompt,
            message_history_json=None,
            conversation_id=f"eval:{spec.name}",
        )
        print(f"> {prompt}\n{result.output}\n")


if __name__ == "__main__":
    asyncio.run(main())
