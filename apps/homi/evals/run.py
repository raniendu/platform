from __future__ import annotations

import asyncio

from homi.agent import build_agent_runner
from homi.settings import HomiSettings
from homi.spec import load_spec


async def main() -> None:
    settings = HomiSettings()
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
