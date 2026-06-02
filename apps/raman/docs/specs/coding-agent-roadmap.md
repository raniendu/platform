# Roadmap: Coding Agent for Raman

> Snapshot updated May 2026 — status callouts reflect implementation state as
> of 2026-05-29. Phased lowest-risk-first.
>
> Companion to the [coding-agent.md](coding-agent.md) design spec and to Axis 1
> (Multi-agent) of [../architecture_roadmap.md](../architecture_roadmap.md).

Each phase lists scope, files touched, and exit criteria. Personal scale
throughout — ship a phase, use it, then decide whether the next is worth it.

## Phase 0 — Spec & decisions `[done]`

Agree the shape: surface = CLI (`raman/cli.py`), cwd = workspace, a strong
model provider, and an approval gate for destructive tools.

- **Files:** `apps/raman/docs/specs/coding-agent.md`, this roadmap.
- **Exit:** design spec reviewed; provider choice and approval model agreed.

## Phase 1 — Read-only repo Q&A `[done]`

The lowest-risk slice: a coding agent that can read and search a repo but not
change it.

- **Scope:** `read_file`, `glob`, `grep` tools; new `spec/coder/agent.toml` +
  `system_prompt.md` on the existing `digitalocean` Gemma4 provider — no model
  code change.
- **Files:** `raman/tools.py` (new tools + `TOOL_REGISTRY`), `spec/coder/`.
- **Exit:** `uv run raman --agent coder` can inspect the current working
  directory with cwd-scoped `read_file`, `glob`, and `grep`. Sensitive paths and
  paths outside cwd are refused.

## Phase 2 — Edits with approval `[done]`

- **Scope:** `write_file` and `edit_file` (string-replace), each explicitly defined
  as deferred/unapproved tools (`Tool(..., requires_approval=True)`). The CLI
  resolves Pydantic AI deferred approval requests inline with
  `HandleDeferredToolCalls`, prompting before execution.
- **Files:** `raman/tools.py` (write/edit tools configured for approval), `raman/cli.py`
  (handling unapproved tool calls).
- **Exit:** agent proposes an edit, the user approves, the file changes;
  declining leaves the working tree untouched.

## Phase 3 — Command execution `[done]`

- **Scope:** read-only `inspect_command` without approval for constrained git
  inspection, plus `run_command` behind approval **and** a conservative
  allowlist (tests, formatters, `git switch <branch>`, `git pull --ff-only`).
- **Files:** `raman/tools.py` (`inspect_command`, `run_command`, allowlists),
  `spec/coder/system_prompt.md`.
- **Exit:** can inspect git state without approval, run the app's
  tests/formatters with per-command confirmation, and switch branches or pull
  fast-forward updates after approval; disallowed commands are refused without
  prompting.

## Phase 4 — MCP compatibility (platform-wide) `[planned]`

Add MCP toolset support to the shared agent factory so any agent can mount MCP
servers — **additive** to the own tools, not a replacement.

- **Scope:** opt-in `mcp_servers` field on `AgentSpec`; `build_agent()` wires
  configured MCP clients as `toolsets=` on the `Agent`. Coder is the first
  consumer (e.g. a git MCP).
- **Files:** `raman/spec.py` (`AgentSpec`), `raman/agent.py` (`build_agent`),
  `spec/coder/agent.toml`. Shared change — affects all agents, but
  backward-compatible (empty default = no behavior change for
  raman/leo/gobind).
- **Exit:** the coder calls a tool served by a configured MCP server; agents
  with no MCP config are unchanged.

## Phase 5 — Polish & CLI decoupling `[planned]`

- **Scope:** reimplement our own slash-command handling + autosuggest against
  public prompt_toolkit / Rich APIs and **drop the `pydantic_ai._cli` import**
  (`raman/cli.py:152`); diff rendering in the CLI; a git/PR helper; session
  ergonomics (e.g. workspace display in the prompt).
- **Files:** `raman/cli.py`, `raman/tools.py`.
- **Exit:** usable end-to-end on a real change in this monorepo, with **no
  dependency on `pydantic_ai._cli`**.

## Decisions

All initial open questions are resolved; this is the decision log.


- **Model provider** — RESOLVED (2026-05-28): reuse the existing DigitalOcean
  Gemma4 provider, same as the other agents; no new model code. Revisit a
  stronger hosted model only if Phase 1 shows Gemma4 can't drive the tools.
- **Tools vs. MCP** — RESOLVED (2026-05-28): basic file/edit/search/exec are
  own tools; MCP support is added separately as a platform-wide agent
  capability (Phase 4), additive rather than a replacement.
- **Private `_cli` coupling** — RESOLVED (2026-05-28): write our own
  slash-command handling + autosuggest against public APIs and drop the
  `pydantic_ai._cli` import (Phase 5), rather than building further on the
  private module.
