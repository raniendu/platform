from pathlib import Path

import pytest
from pydantic_ai import Tool

from raman import tools


@pytest.mark.asyncio
async def test_read_file_returns_numbered_excerpt(monkeypatch, tmp_path):
    source = tmp_path / "pkg" / "example.py"
    source.parent.mkdir()
    source.write_text("alpha\nbeta\ngamma\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    result = await tools.read_file("pkg/example.py", start_line=2, max_lines=2)

    assert "pkg/example.py:2-3" in result
    assert "2 | beta" in result
    assert "3 | gamma" in result
    assert "1 | alpha" not in result


@pytest.mark.asyncio
async def test_file_tools_refuse_sensitive_paths(monkeypatch, tmp_path):
    secret = tmp_path / ".env.local"
    secret.write_text("TOKEN=secret\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    result = await tools.read_file(".env.local")

    assert "Refusing" in result
    assert "TOKEN" not in result
    assert "secret" not in result


@pytest.mark.asyncio
async def test_file_tools_refuse_paths_outside_cwd(monkeypatch, tmp_path):
    workspace = tmp_path / "workspace"
    outside = tmp_path / "outside.txt"
    workspace.mkdir()
    outside.write_text("outside\n", encoding="utf-8")
    monkeypatch.chdir(workspace)

    result = await tools.read_file(str(outside))

    assert "escapes the workspace" in result
    assert "outside" not in result


@pytest.mark.asyncio
async def test_glob_and_grep_are_cwd_scoped(monkeypatch, tmp_path):
    source = tmp_path / "raman" / "agent.py"
    source.parent.mkdir()
    source.write_text("def build_agent():\n    return 'ok'\n", encoding="utf-8")
    (tmp_path / ".env.local").write_text("build_agent secret\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    glob_result = await tools.glob_paths("**/*.py")
    grep_result = await tools.grep("build_agent")

    assert "raman/agent.py" in glob_result
    assert ".env.local" not in glob_result
    assert "raman/agent.py:1:def build_agent():" in grep_result
    assert "secret" not in grep_result


@pytest.mark.asyncio
async def test_write_and_edit_file_operate_relative_to_cwd(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)

    write_result = await tools.write_file("notes/todo.txt", "hello\n")
    edit_result = await tools.edit_file("notes/todo.txt", "hello", "goodbye")

    assert "Wrote notes/todo.txt" in write_result
    assert "Updated notes/todo.txt" in edit_result
    assert (tmp_path / "notes" / "todo.txt").read_text(encoding="utf-8") == (
        "goodbye\n"
    )


@pytest.mark.asyncio
async def test_edit_file_requires_unique_match(monkeypatch, tmp_path):
    target = tmp_path / "notes.txt"
    target.write_text("same\nsame\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    result = await tools.edit_file("notes.txt", "same", "other")

    assert "matched 2 times" in result
    assert target.read_text(encoding="utf-8") == "same\nsame\n"


@pytest.mark.asyncio
async def test_run_command_uses_allowlist(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)

    denied = await tools.run_command("echo hello")
    allowed = await tools.run_command("git status --short")

    assert "not allowlisted" in denied
    assert "echo" in denied
    assert "git status --short" in allowed


def test_destructive_tools_require_pydantic_ai_approval():
    for name in ("write_file", "edit_file", "run_command"):
        tool = tools.TOOL_REGISTRY[name]

        assert isinstance(tool, Tool)
        assert tool.requires_approval is True


def test_read_only_tools_do_not_require_approval():
    for name in ("read_file", "glob", "grep"):
        assert not isinstance(tools.TOOL_REGISTRY[name], Tool)
