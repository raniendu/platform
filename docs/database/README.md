# Database Documentation

This directory documents datastore ownership for the platform apps. The DBML
file is intended to stay parseable by PyDBML and related DBML tooling.

- [`platform-app-datastores.dbml`](platform-app-datastores.dbml) describes the
  logical app datastore model and relationships.

The app-owned table layouts for Prefect, Airflow, Paperclip, Raman, Homi, and Vikram are
intentionally not copied here. Those products own their internal migration
histories, and this repository only wires their databases, roles, connection
variables, and volumes.
If table-level schema docs become useful, generate them from the active upstream
schema rather than hand-maintaining stale vendor internals.

## Logical Datastores

| App | Datastore | Local | Production | Migration owner |
| --- | --- | --- | --- | --- |
| DotDev | File-backed posts and assets | Source tree | Source tree in image | This repo |
| Prefect | Postgres metadata | `prefect-postgres` / `prefect` | `platform-postgres` / `prefect` | Prefect |
| Flow / Airflow | Postgres metadata plus logs/plugins/config volumes | `airflow-postgres` / `airflow` | `platform-postgres` / `airflow` | Airflow |
| Paperclip | Postgres metadata plus `/paperclip` data volume | `paperclip-postgres` / `paperclip` | `platform-postgres` / `paperclip` | Paperclip |
| Raman | SQLite thread history plus DBOS workflow state in `/app/.raman` | `raman-state` | `raman-state` | Raman |
| Homi | SQLite thread history plus Strands/DBOS state in `/app/.homi` | `homi-state` | `homi-state` | Homi |
| Vikram | SQLite thread history plus ADK/DBOS state in `/app/.vikram` | `vikram-state` | `vikram-state` | Vikram |

## PyDBML Parse Check

If PyDBML is installed in the active Python environment, parse the DBML file
with:

```bash
python -c "from pydbml import PyDBML; PyDBML(open('docs/database/platform-app-datastores.dbml', encoding='utf-8').read())"
```
