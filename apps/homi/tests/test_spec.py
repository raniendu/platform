from pathlib import Path

import pytest

from homi.settings import HomiSettings
from homi.spec import load_spec


def test_load_real_homi_spec():
    settings = HomiSettings(_env_file=None)
    spec = load_spec("homi", settings.spec_root)

    assert spec.name == "homi"
    assert spec.description.startswith("Personal assistant")
    assert "personal AI assistant" in spec.instructions


def _write_agent_spec(agent_dir: Path, body: str) -> None:
    agent_dir.mkdir(parents=True, exist_ok=True)
    (agent_dir / "agent.toml").write_text(body)


def test_local_context_file_is_appended(tmp_path):
    agent_dir = tmp_path / "demo"
    _write_agent_spec(
        agent_dir,
        """
name = "demo"
description = "demo"
system_prompt = "system_prompt.md"
context_files = ["notes.md"]
""",
    )
    (agent_dir / "system_prompt.md").write_text("PROMPT")
    (agent_dir / "notes.md").write_text("LOCAL_CTX")

    spec = load_spec("demo", tmp_path)

    assert spec.instructions == "PROMPT\n\nLOCAL_CTX"


def test_shared_context_file_is_appended(tmp_path):
    agent_dir = tmp_path / "demo"
    _write_agent_spec(
        agent_dir,
        """
name = "demo"
description = "demo"
system_prompt = "system_prompt.md"
shared_context_files = ["context/style.md"]
""",
    )
    (agent_dir / "system_prompt.md").write_text("PROMPT")
    shared_ctx = tmp_path / "shared" / "context"
    shared_ctx.mkdir(parents=True)
    (shared_ctx / "style.md").write_text("SHARED_CTX")

    spec = load_spec("demo", tmp_path)

    assert spec.instructions == "PROMPT\n\nSHARED_CTX"


def test_shared_then_local_order(tmp_path):
    agent_dir = tmp_path / "demo"
    _write_agent_spec(
        agent_dir,
        """
name = "demo"
description = "demo"
system_prompt = "system_prompt.md"
context_files = ["notes.md"]
shared_context_files = ["context/style.md"]
""",
    )
    (agent_dir / "system_prompt.md").write_text("PROMPT")
    (agent_dir / "notes.md").write_text("LOCAL_CTX")
    shared_ctx = tmp_path / "shared" / "context"
    shared_ctx.mkdir(parents=True)
    (shared_ctx / "style.md").write_text("SHARED_CTX")

    spec = load_spec("demo", tmp_path)

    assert spec.instructions == "PROMPT\n\nSHARED_CTX\n\nLOCAL_CTX"


def test_missing_spec_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        load_spec("missing", tmp_path)
