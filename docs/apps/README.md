# App Architecture Docs

This directory contains app-level architecture notes for each runtime surface in
the platform monorepo. Use these when changing app code; use the shared
[architecture](../architecture.md), [deployment](../deployment.md), and
[operations](../operations.md) docs when changing hosting, routing, workflows,
or production flags.

| App | Runtime | Production flag | Doc |
| --- | --- | --- | --- |
| DotDev | Flask site | `DEPLOY_DOTDEV` | [DotDev](dotdev-architecture.md) |
| Prefect | Prefect server and worker | `DEPLOY_PREFECT` | [Prefect](prefect-architecture.md) |
| Flow | Airflow webserver and scheduler | `DEPLOY_FLOW` | [Flow / Airflow](flow-architecture.md) |
| Raman | Pydantic AI FastAPI agent | `DEPLOY_RAMAN` | [Raman](raman-architecture.md) |

Each app document should cover code boundaries, runtime flow, data ownership,
configuration, and the narrowest useful validation command for that app.
