# Homi Deployment

Homi is deprecated as a platform app. Its shared local Compose service,
production Compose profile, Caddy routes, image build, and deploy flag have
been removed. This document is retained only for archived direct-app context.

## Direct Local Run

```bash
uv sync --project apps/homi --locked
uv run --project apps/homi homi-api
curl http://127.0.0.1:8000/healthz
```

## Production

There is no supported Homi production deployment path in the shared platform
stack.
