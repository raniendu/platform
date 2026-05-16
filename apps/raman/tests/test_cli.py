import importlib
import json
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

APP_ROOT = Path(__file__).resolve().parents[1]


def test_cli_file_execution_shows_help():
    result = subprocess.run(
        [sys.executable, str(APP_ROOT / "raman" / "cli.py"), "--help"],
        capture_output=True,
        check=False,
        cwd=APP_ROOT,
        text=True,
    )

    assert result.returncode == 0
    assert "usage: raman" in result.stdout
    assert "--agent" in result.stdout
    assert "--once" in result.stdout
    assert "--prompt" in result.stdout
    assert "--json" in result.stdout


class FakeSettings:
    default_agent = "raman"
    spec_root = APP_ROOT / "spec"

    def model_copy(self, *, update):
        copied = FakeSettings()
        copied.default_agent = update.get("default_agent", self.default_agent)
        copied.spec_root = self.spec_root
        return copied


class FakeAgent:
    def __init__(self, calls):
        self.calls = calls

    def run_sync(self, prompt):
        self.calls.append(prompt)
        return SimpleNamespace(output=f"reply: {prompt}")

    def to_cli_sync(self, *, prog_name):
        self.calls.append(f"interactive:{prog_name}")


def patch_cli_dependencies(monkeypatch):
    calls = []

    agent_module = importlib.import_module("raman.agent")
    settings_module = importlib.import_module("raman.settings")
    spec_module = importlib.import_module("raman.spec")

    monkeypatch.setattr(settings_module, "RamanSettings", FakeSettings)
    monkeypatch.setattr(
        spec_module,
        "load_spec",
        lambda name, spec_root: SimpleNamespace(name=name.title()),
    )
    monkeypatch.setattr(
        agent_module,
        "build_agent",
        lambda *, spec, settings: FakeAgent(calls),
    )
    return calls


def test_cli_once_runs_prompt_string(monkeypatch, capsys):
    from raman.cli import main

    calls = patch_cli_dependencies(monkeypatch)

    main(["--once", "--prompt", "say hello"])

    assert calls == ["say hello"]
    assert capsys.readouterr().out == "reply: say hello\n"


def test_cli_once_reads_prompt_from_file(monkeypatch, capsys, tmp_path):
    from raman.cli import main

    prompt_file = tmp_path / "prompt.txt"
    prompt_file.write_text("from file\n", encoding="utf-8")
    calls = patch_cli_dependencies(monkeypatch)

    main(["--once", "--prompt", str(prompt_file)])

    assert calls == ["from file\n"]
    assert capsys.readouterr().out == "reply: from file\n\n"


def test_cli_once_reads_prompt_from_at_file(monkeypatch, capsys, tmp_path):
    from raman.cli import main

    prompt_file = tmp_path / "prompt.txt"
    prompt_file.write_text("from at-file", encoding="utf-8")
    calls = patch_cli_dependencies(monkeypatch)

    main(["--once", "--prompt", f"@{prompt_file}"])

    assert calls == ["from at-file"]
    assert capsys.readouterr().out == "reply: from at-file\n"


def test_cli_once_json_outputs_agent_and_output(monkeypatch, capsys):
    from raman.cli import main

    calls = patch_cli_dependencies(monkeypatch)

    main(["--agent", "leo", "--once", "--prompt", "status", "--json"])

    assert calls == ["status"]
    assert json.loads(capsys.readouterr().out) == {
        "agent": "Leo",
        "output": "reply: status",
    }


def test_prompt_requires_once(capsys):
    from raman.cli import main

    try:
        main(["--prompt", "status"])
    except SystemExit as exc:
        assert exc.code == 2
    else:
        raise AssertionError("Expected parser error")

    assert "--prompt requires --once" in capsys.readouterr().err
