# Homi Current Architecture

Homi is a FastAPI service around a Strands SDK agent. It mirrors Raman's
platform surface while keeping SDK-specific runtime state inside `apps/homi`.

## Request Flow

- `/chat` builds a fresh `HomiAgentRunner`, invokes Strands once, and returns the final text.
- `/threads/{interface}/{thread}/messages` enqueues a DBOS workflow.
- The workflow loads the thread row from SQLite, rebuilds a Strands agent with the stored `agent.messages` JSON, runs the prompt, and stores the updated messages.
- `/telegram/webhook` validates Telegram's secret header, deduplicates update IDs, handles `/start`, `/help`, `/reset`, and `/agent <name>`, then enqueues normal text messages.

## State

- Thread metadata and Strands message history: `.homi/homi.sqlite3`
- DBOS workflow state: `.homi/dbos.sqlite3`
- Local Compose volume: `homi-state`
- Production Compose volume: `homi-state`

## Runtime

Homi uses Strands with Amazon Bedrock by default. Model configuration is
`HOMI_MODEL_ID` and `HOMI_AWS_REGION`; credentials use standard AWS environment
variables or `AWS_BEARER_TOKEN_BEDROCK`.

The `web_search` tool is a Strands `@tool` wrapper around Parallel search. Set
`HOMI_PARALLEL_API_KEY` or shared `PARALLEL_API_KEY` to enable it.
