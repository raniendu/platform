# Homi Tools

Tools are declared by name in `spec/<agent>/agent.toml` and resolved through
`homi.tools.TOOL_REGISTRY`.

`web_search` is implemented as a Strands `@tool` function. It calls Parallel
Search and returns a compact markdown summary of up to five results.

Configuration:

```env
HOMI_PARALLEL_API_KEY=
# or shared fallback
PARALLEL_API_KEY=
```

Offline tests should mock tool callables or the Parallel client. Do not make
default tests depend on network access.
