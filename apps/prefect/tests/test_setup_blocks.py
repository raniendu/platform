from __future__ import annotations

import importlib.util
import types
from pathlib import Path


def load_setup_blocks_module() -> types.ModuleType:
    script_path = Path(__file__).resolve().parents[1] / "scripts" / "setup-blocks.py"
    spec = importlib.util.spec_from_file_location("setup_blocks", script_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_setup_pushover_blocks_saves_prefect_secret_blocks(
    monkeypatch,
    capsys,
) -> None:
    module = load_setup_blocks_module()
    saved_blocks: dict[str, str] = {}

    class FakeSecret:
        def __init__(self, value: str) -> None:
            self.value = value

        def save(self, name: str, overwrite: bool = False):
            saved_blocks[name] = self.value
            assert overwrite is True

    class FakeResponse:
        def json(self):
            return {"status": 1}

    monkeypatch.setenv("PUSHOVER_APP_TOKEN", "test-app-token")
    monkeypatch.setenv("PUSHOVER_USER_KEY", "test-user-key")
    monkeypatch.setattr(module, "Secret", FakeSecret, raising=False)
    monkeypatch.setattr(module.httpx, "post", lambda *args, **kwargs: FakeResponse())

    assert module.main() == 0

    assert saved_blocks == {
        "pushover-app-token": "test-app-token",
        "pushover-user-key": "test-user-key",
    }
    output = capsys.readouterr().out
    assert "pushover-app-token" in output
    assert "pushover-user-key" in output
    assert "test-app-token" not in output
    assert "test-user-key" not in output
