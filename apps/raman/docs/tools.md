# Tools

Tools are async Python callables, or explicit `pydantic_ai.Tool` wrappers, that
the agent can invoke during a run. They live in `raman/tools.py`, registered by
name in `TOOL_REGISTRY`, and are referenced by name from each agent's
`agent.toml` under `tools = [...]`.

## How a tool flows through the system

1. `raman.tools.TOOL_REGISTRY` maps a string name to an `async def` callable or
   a `Tool(...)` wrapper.
2. Each agent spec lists the tools it wants: `tools = ["web_search"]`.
3. `raman.agent.build_agent` resolves names against the registry and passes
   the callables to `pydantic_ai.Agent(..., tools=[...])`.
4. Pydantic AI inspects each callable's signature and docstring to build the
   tool schema sent to the model. Argument types become the JSON schema; the
   docstring becomes the description the model sees.

That last point is load-bearing: the model only chooses a tool well if the
docstring describes *when* to use it and the parameter types are explicit.

## Adding a tool

Two edits, in this order.

### 1. Register the callable

```python
# raman/tools.py
async def get_weather(city: str) -> str:
    """Return the current weather for a city.

    Use this only when the user asks about weather. Returns a short
    natural-language description, not structured data.

    Args:
        city: City name, e.g. "Bengaluru" or "San Francisco".
    """
    ...


TOOL_REGISTRY: dict[str, Callable[..., Awaitable[str]]] = {
    "web_search": web_search,
    "get_weather": get_weather,
}
```

Conventions:

- **Async only.** The agent's run loop is async; sync tools would block it.
- **Return a `str`.** Models work better with prose than with JSON blobs.
  If you need structure, format it as Markdown inside the string.
- **Type every parameter.** Untyped parameters degrade the schema the model
  receives.
- **Docstring describes *when* to use the tool**, not just what it does.
  The first line should answer "why would the model pick this?".
- **Wrap destructive tools.** Tools that write files or execute commands should
  be registered as `Tool(function, requires_approval=True)` and exposed only on
  surfaces that can handle deferred approvals.

### 2. Reference it from a spec

```toml
# spec/<agent>/agent.toml
tools = ["web_search", "get_weather"]
```

Tool names are resolved at agent build time. An unknown name raises
`KeyError` from `build_agent`, which surfaces as a startup failure — there
is no silent fallback.

## Configuration and secrets

Tools that need API keys or other secrets read them from `RamanSettings`,
not from `os.environ` directly. Add the field to `RamanSettings`, expose an
env-var alias, document it in `.env.example` and the README configuration
table, then read it inside the tool.

`web_search` is the worked example:

```python
@lru_cache(maxsize=1)
def _parallel_client() -> AsyncParallel:
    settings = RamanSettings()
    if not settings.parallel_api_key:
        raise RuntimeError(
            "PARALLEL_API_KEY is not set. Add it to .env to enable web_search."
        )
    return AsyncParallel(api_key=settings.parallel_api_key)
```

Three things worth copying:

- **Lazy client construction.** The client is built on first use, not at
  import time, so the import works even when the secret is missing.
- **Cache the client.** `lru_cache(maxsize=1)` reuses one HTTP client across
  every tool call.
- **Loud failure.** Raise with a message that names the env var and how to
  fix it. The model will see the error string and can relay it.

## Testing tools

Unit-test the callable directly with `pytest-asyncio`. Patch the upstream
client (e.g., `AsyncParallel`) rather than hitting the live API. For
integration tests that exercise tool selection, gate them behind
`RAMAN_RUN_EVALS=1` along with the rest of the live LLM-judge suite.

## When *not* to add a tool

If the answer is always derivable from local files or static config, prefer
adding a context file (under `spec/<agent>/context/` or `spec/shared/
context/`) and listing it in the spec. Tools should be reserved for things
that change at runtime, depend on external systems, or require computation
the model cannot do reliably (current dates, math, web lookups).
