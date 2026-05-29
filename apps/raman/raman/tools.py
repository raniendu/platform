from __future__ import annotations

import asyncio
import fnmatch
import os
import re
import shlex
from datetime import datetime
from functools import lru_cache
from pathlib import Path
from typing import Awaitable, Callable, Literal

from parallel import AsyncParallel
from pydantic_ai import RunContext, Tool

from raman.grocery import GroceryListStore
from raman.settings import RamanSettings

MAX_FILE_LINES = 200
MAX_GLOB_MATCHES = 200
MAX_GREP_MATCHES = 100
MAX_COMMAND_OUTPUT_CHARS = 12_000
DEFAULT_COMMAND_TIMEOUT_SECONDS = 60

SKIPPED_DIR_NAMES = {
    ".git",
    ".hg",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".svn",
    ".venv",
    "__pycache__",
    "node_modules",
    "venv",
}
SENSITIVE_NAMES = {
    ".env",
    ".env.local",
    ".env.production",
    ".env.production.credentials",
    ".env.production.generated",
    "id_dsa",
    "id_ecdsa",
    "id_ed25519",
    "id_rsa",
    "terraform.tfstate",
    "terraform.tfstate.backup",
}
SENSITIVE_DIR_NAMES = {
    ".ssh",
    ".terraform",
    "secrets",
}
SENSITIVE_SUFFIXES = {
    ".key",
    ".p12",
    ".pem",
    ".pfx",
    ".tfstate",
    ".tfstate.backup",
}
UV_RUN_OPTIONS_WITH_VALUE = {
    "--config-file",
    "--directory",
    "--env-file",
    "--extra",
    "--group",
    "--index",
    "--index-url",
    "--project",
    "--with",
    "--with-editable",
    "--with-requirements",
}


@lru_cache(maxsize=1)
def _parallel_client() -> AsyncParallel:
    settings = RamanSettings()
    if not settings.parallel_api_key:
        raise RuntimeError(
            "PARALLEL_API_KEY is not set. Add it to .env to enable web_search."
        )
    return AsyncParallel(api_key=settings.parallel_api_key)


async def web_search(query: str) -> str:
    """Search the public web for current or factual information.

    Use this when the answer depends on information you do not already know,
    such as recent events, prices, dates, documentation, or anything that may
    have changed.

    Args:
        query: A concise natural-language search query, ideally 3-10 words.
    """
    response = await _parallel_client().search(
        search_queries=[query],
        objective=query,
        mode="basic",
    )
    if not response.results:
        return f"No results for: {query}"

    blocks: list[str] = []
    for r in response.results[:5]:
        title = r.title or r.url
        excerpt = "\n".join(r.excerpts) if r.excerpts else ""
        blocks.append(f"## {title}\n{r.url}\n\n{excerpt}".rstrip())
    return "\n\n---\n\n".join(blocks)


def _workspace_root() -> Path:
    return Path.cwd().resolve()


def _resolve_workspace_path(path: str) -> Path | None:
    root = _workspace_root()
    candidate = Path(path).expanduser()
    if not candidate.is_absolute():
        candidate = root / candidate
    try:
        resolved = candidate.resolve(strict=False)
    except OSError:
        return None
    if resolved == root or root in resolved.parents:
        return resolved
    return None


def _relative_path(path: Path) -> str:
    try:
        return path.relative_to(_workspace_root()).as_posix()
    except ValueError:
        return path.name


def _is_sensitive_path(path: Path) -> bool:
    try:
        relative = path.relative_to(_workspace_root())
    except ValueError:
        return True
    for part in relative.parts:
        lower = part.lower()
        if lower == ".env.example":
            continue
        if lower.startswith(".env"):
            return True
        if lower in SENSITIVE_NAMES or lower in SENSITIVE_DIR_NAMES:
            return True
        if any(lower.endswith(suffix) for suffix in SENSITIVE_SUFFIXES):
            return True
    return False


def _is_skipped_path(path: Path) -> bool:
    try:
        relative = path.relative_to(_workspace_root())
    except ValueError:
        return True
    return any(part in SKIPPED_DIR_NAMES for part in relative.parts)


def _iter_workspace_files(root: Path) -> list[Path]:
    if root.is_file():
        return [root]

    files: list[Path] = []
    for dirpath, dirnames, filenames in os.walk(root):
        current = Path(dirpath)
        dirnames[:] = [
            dirname
            for dirname in dirnames
            if dirname not in SKIPPED_DIR_NAMES
            and not _is_sensitive_path(current / dirname)
        ]
        for filename in filenames:
            files.append(current / filename)
    return sorted(files)


def _refusal(message: str) -> str:
    return f"Refusing: {message}"


async def read_file(
    path: str,
    start_line: int = 1,
    max_lines: int = MAX_FILE_LINES,
) -> str:
    """Read a text file from the current working directory.

    Use this to inspect source, tests, docs, or configuration in the local
    workspace. Paths are resolved relative to cwd. Sensitive files and paths
    outside cwd are refused.

    Args:
        path: File path to read, relative to cwd unless absolute.
        start_line: First 1-based line number to include.
        max_lines: Maximum number of lines to return.
    """
    resolved = _resolve_workspace_path(path)
    if resolved is None:
        return _refusal("path escapes the workspace.")
    if _is_sensitive_path(resolved):
        return _refusal("sensitive paths cannot be read.")
    if not resolved.exists():
        return f"File not found: {_relative_path(resolved)}"
    if not resolved.is_file():
        return f"Not a file: {_relative_path(resolved)}"
    if start_line < 1:
        return "start_line must be at least 1."
    if max_lines < 1:
        return "max_lines must be at least 1."

    try:
        text = resolved.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return f"Cannot read non-UTF-8 file: {_relative_path(resolved)}"
    except OSError as exc:
        return f"Could not read {_relative_path(resolved)}: {exc}"

    lines = text.splitlines()
    if not lines:
        return f"# {_relative_path(resolved)}: empty file"
    if start_line > len(lines):
        return (
            f"# {_relative_path(resolved)} has {len(lines)} lines; "
            f"start_line {start_line} is past the end."
        )

    end_line = min(len(lines), start_line + max_lines - 1)
    width = len(str(end_line))
    body = "\n".join(
        f"{line_no:>{width}} | {lines[line_no - 1]}"
        for line_no in range(start_line, end_line + 1)
    )
    suffix = "\n... truncated" if end_line < len(lines) else ""
    return f"# {_relative_path(resolved)}:{start_line}-{end_line}\n{body}{suffix}"


async def glob(pattern: str, max_matches: int = MAX_GLOB_MATCHES) -> str:
    """Find files in the current working directory with a glob pattern.

    Use this to discover source files by path. The pattern must be relative to
    cwd. Sensitive paths, skipped runtime directories, and paths outside cwd are
    omitted.

    Args:
        pattern: Relative glob pattern such as "**/*.py".
        max_matches: Maximum number of matching file paths to return.
    """
    if max_matches < 1:
        return "max_matches must be at least 1."
    if Path(pattern).expanduser().is_absolute() or ".." in Path(pattern).parts:
        return _refusal("glob patterns must stay inside the workspace.")

    root = _workspace_root()
    matches: list[str] = []
    try:
        candidates = sorted(root.glob(pattern))
    except ValueError as exc:
        return f"Invalid glob pattern: {exc}"

    for candidate in candidates:
        if len(matches) >= max_matches:
            break
        if not candidate.is_file():
            continue
        resolved = candidate.resolve(strict=False)
        if _is_skipped_path(resolved) or _is_sensitive_path(resolved):
            continue
        matches.append(_relative_path(resolved))

    if not matches:
        return f"No files matched: {pattern}"
    suffix = "\n... truncated" if len(matches) == max_matches else ""
    return "\n".join(matches) + suffix


glob_paths = glob


async def grep(
    pattern: str,
    path: str = ".",
    include: str | None = None,
    max_matches: int = MAX_GREP_MATCHES,
) -> str:
    """Search text files in the current working directory with a regex.

    Use this to find where symbols, strings, or behavior are implemented.
    Sensitive paths, skipped runtime directories, binary files, and paths outside
    cwd are omitted.

    Args:
        pattern: Python regular expression to search for.
        path: File or directory to search, relative to cwd unless absolute.
        include: Optional glob filter for relative file paths, e.g. "*.py".
        max_matches: Maximum number of matching lines to return.
    """
    resolved = _resolve_workspace_path(path)
    if resolved is None:
        return _refusal("path escapes the workspace.")
    if _is_sensitive_path(resolved):
        return _refusal("sensitive paths cannot be searched.")
    if max_matches < 1:
        return "max_matches must be at least 1."
    try:
        regex = re.compile(pattern)
    except re.error as exc:
        return f"Invalid regex: {exc}"

    if not resolved.exists():
        return f"Path not found: {_relative_path(resolved)}"
    candidates = _iter_workspace_files(resolved)

    matches: list[str] = []
    for candidate in candidates:
        if len(matches) >= max_matches:
            break
        if not candidate.is_file():
            continue
        candidate = candidate.resolve(strict=False)
        rel = _relative_path(candidate)
        if _is_skipped_path(candidate) or _is_sensitive_path(candidate):
            continue
        if include is not None and not fnmatch.fnmatch(rel, include):
            continue
        try:
            text = candidate.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        for line_no, line in enumerate(text.splitlines(), start=1):
            if regex.search(line):
                matches.append(f"{rel}:{line_no}:{line}")
                if len(matches) >= max_matches:
                    break

    if not matches:
        return f"No matches for: {pattern}"
    suffix = "\n... truncated" if len(matches) == max_matches else ""
    return "\n".join(matches) + suffix


async def write_file(path: str, content: str) -> str:
    """Write a UTF-8 text file in the current working directory.

    Use this only when the user has asked for a file creation or replacement.
    This tool requires explicit human approval before Pydantic AI executes it.

    Args:
        path: File path to write, relative to cwd unless absolute.
        content: Complete file contents to write.
    """
    resolved = _resolve_workspace_path(path)
    if resolved is None:
        return _refusal("path escapes the workspace.")
    if _is_sensitive_path(resolved):
        return _refusal("sensitive paths cannot be written.")
    if resolved.exists() and resolved.is_dir():
        return f"Not a file: {_relative_path(resolved)}"
    try:
        resolved.parent.mkdir(parents=True, exist_ok=True)
        resolved.write_text(content, encoding="utf-8")
    except OSError as exc:
        return f"Could not write {_relative_path(resolved)}: {exc}"
    return f"Wrote {_relative_path(resolved)} ({len(content)} characters)."


async def edit_file(
    path: str,
    old_text: str,
    new_text: str,
    replace_all: bool = False,
) -> str:
    """Edit a UTF-8 text file by replacing exact text.

    Use this for small, targeted edits after reading the file. By default the
    old text must match exactly once, which prevents accidental broad changes.
    This tool requires explicit human approval before Pydantic AI executes it.

    Args:
        path: File path to edit, relative to cwd unless absolute.
        old_text: Exact text to replace.
        new_text: Replacement text.
        replace_all: Replace every match instead of requiring one unique match.
    """
    resolved = _resolve_workspace_path(path)
    if resolved is None:
        return _refusal("path escapes the workspace.")
    if _is_sensitive_path(resolved):
        return _refusal("sensitive paths cannot be edited.")
    if not resolved.exists():
        return f"File not found: {_relative_path(resolved)}"
    if not resolved.is_file():
        return f"Not a file: {_relative_path(resolved)}"
    if old_text == "":
        return "old_text must not be empty."

    try:
        text = resolved.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return f"Cannot edit non-UTF-8 file: {_relative_path(resolved)}"
    except OSError as exc:
        return f"Could not read {_relative_path(resolved)}: {exc}"

    count = text.count(old_text)
    if count == 0:
        return f"No match found in {_relative_path(resolved)}."
    if count > 1 and not replace_all:
        return (
            f"old_text matched {count} times in {_relative_path(resolved)}; "
            "set replace_all=true to replace every match."
        )

    updated = (
        text.replace(old_text, new_text)
        if replace_all
        else text.replace(old_text, new_text, 1)
    )
    try:
        resolved.write_text(updated, encoding="utf-8")
    except OSError as exc:
        return f"Could not write {_relative_path(resolved)}: {exc}"
    replaced = count if replace_all else 1
    return f"Updated {_relative_path(resolved)} ({replaced} replacement)."


def _is_allowed_command(argv: list[str]) -> bool:
    if not argv:
        return False
    executable = Path(argv[0]).name
    if executable == "git":
        return len(argv) >= 2 and argv[1] in {"diff", "status"}
    if executable in {"black", "isort", "pre-commit", "pytest"}:
        return True
    if executable.startswith("python"):
        return (
            len(argv) >= 3
            and argv[1] == "-m"
            and argv[2]
            in {
                "black",
                "isort",
                "pytest",
            }
        )
    if executable == "uv":
        return _is_allowed_uv_run(argv)
    return False


def _is_allowed_uv_run(argv: list[str]) -> bool:
    if len(argv) < 3 or argv[1] != "run":
        return False
    index = 2
    while index < len(argv):
        token = argv[index]
        if token == "--":
            index += 1
            break
        if token in UV_RUN_OPTIONS_WITH_VALUE:
            index += 2
            continue
        if any(token.startswith(f"{option}=") for option in UV_RUN_OPTIONS_WITH_VALUE):
            index += 1
            continue
        if token.startswith("-"):
            index += 1
            continue
        break
    return _is_allowed_command(argv[index:])


def _truncate_output(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    return text[:limit] + "\n... output truncated"


async def run_command(
    command: str,
    timeout_seconds: int = DEFAULT_COMMAND_TIMEOUT_SECONDS,
    max_output_chars: int = MAX_COMMAND_OUTPUT_CHARS,
) -> str:
    """Run an allowlisted command in the current working directory.

    Use this for validation commands only: tests, formatters, and safe git
    inspection commands such as git status or git diff. The command is parsed
    with shlex and executed without a shell. This tool requires explicit human
    approval before Pydantic AI executes it.

    Args:
        command: Command string, e.g. "uv run pytest tests -q".
        timeout_seconds: Seconds to wait before killing the process.
        max_output_chars: Maximum combined output characters to return.
    """
    try:
        argv = shlex.split(command)
    except ValueError as exc:
        return f"Invalid command: {exc}"
    if not _is_allowed_command(argv):
        executable = argv[0] if argv else ""
        return f"Command is not allowlisted: {executable or command}"
    if timeout_seconds < 1:
        return "timeout_seconds must be at least 1."
    if max_output_chars < 1:
        return "max_output_chars must be at least 1."

    try:
        process = await asyncio.create_subprocess_exec(
            *argv,
            cwd=_workspace_root(),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
    except FileNotFoundError:
        return f"Command not found: {argv[0]}"
    except OSError as exc:
        return f"Could not run {command}: {exc}"

    try:
        stdout_bytes, stderr_bytes = await asyncio.wait_for(
            process.communicate(), timeout=timeout_seconds
        )
    except TimeoutError:
        process.kill()
        stdout_bytes, stderr_bytes = await process.communicate()
        stdout = stdout_bytes.decode("utf-8", errors="replace")
        stderr = stderr_bytes.decode("utf-8", errors="replace")
        return _truncate_output(
            f"$ {command}\nTimed out after {timeout_seconds}s.\n"
            f"stdout:\n{stdout}\nstderr:\n{stderr}".rstrip(),
            max_output_chars,
        )

    stdout = stdout_bytes.decode("utf-8", errors="replace").strip()
    stderr = stderr_bytes.decode("utf-8", errors="replace").strip()
    sections = [f"$ {command}", f"exit code: {process.returncode}"]
    if stdout:
        sections.append(f"stdout:\n{stdout}")
    if stderr:
        sections.append(f"stderr:\n{stderr}")
    return _truncate_output("\n".join(sections), max_output_chars)


async def grocery_list(
    ctx: RunContext[None],
    action: Literal["show", "add", "remove", "mark_bought", "clear"],
    item: str | None = None,
) -> str:
    """Manage this chat's grocery list.

    Use this when the user asks to show, add to, remove from, mark bought on,
    or clear the grocery list. Lists are scoped to the current conversation.

    Args:
        action: The operation to perform: show, add, remove, mark_bought, or clear.
        item: Grocery item name. Required for add, remove, and mark_bought.
    """
    scope = ctx.conversation_id or "default"
    store = GroceryListStore(RamanSettings().grocery_list_path)

    try:
        if action == "show":
            items = store.list_items(scope)
            if not items:
                return "Grocery list is empty for this chat."
            lines = [f"- {entry.item} (added {entry.added_date})" for entry in items]
            return "Grocery list:\n" + "\n".join(lines)

        if action == "add":
            result = store.add_item(
                scope,
                item,
                added_date=datetime.now().astimezone().date().isoformat(),
            )
            if result.created:
                return (
                    f"Added {result.item.item} to this chat's grocery list "
                    f"on {result.item.added_date}."
                )
            return (
                f"{result.item.item} is already on this chat's grocery list "
                f"(added {result.item.added_date})."
            )

        if action == "remove":
            removed = store.remove_item(scope, item)
            if removed is None:
                return f"{item} is not on this chat's grocery list."
            return (
                f"Removed {removed.item} from this chat's grocery list "
                f"(added {removed.added_date})."
            )

        if action == "mark_bought":
            removed = store.remove_item(scope, item)
            if removed is None:
                return f"{item} is not on this chat's grocery list."
            return (
                f"Marked {removed.item} as bought and removed it from this "
                f"chat's grocery list (added {removed.added_date})."
            )

        if action == "clear":
            count = store.clear(scope)
            if count == 0:
                return "Grocery list is already empty for this chat."
            noun = "item" if count == 1 else "items"
            return f"Cleared {count} {noun} from this chat's grocery list."
    except ValueError as exc:
        if (
            action in {"add", "remove", "mark_bought"}
            and str(exc) == "item is required"
        ):
            return f"Grocery list error: item is required for {action}."
        return f"Grocery list error: {exc}"

    return f"Grocery list error: unsupported action {action!r}."


ToolEntry = Callable[..., Awaitable[str]] | Tool[None]


TOOL_REGISTRY: dict[str, ToolEntry] = {
    "web_search": web_search,
    "grocery_list": grocery_list,
    "read_file": read_file,
    "glob": glob,
    "grep": grep,
    "write_file": Tool(write_file, requires_approval=True, sequential=True),
    "edit_file": Tool(edit_file, requires_approval=True, sequential=True),
    "run_command": Tool(run_command, requires_approval=True, sequential=True),
}
