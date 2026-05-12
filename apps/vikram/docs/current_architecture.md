# Vikram Current Architecture

Vikram is a FastAPI service around a Google ADK agent. It mirrors Raman's
platform surface while keeping ADK-specific runtime state inside `apps/vikram`.

## Request Flow

- `/chat` builds a fresh `VikramAgentRunner`, invokes ADK once, and returns the final text event.
- `/threads/{interface}/{thread}/messages` enqueues a DBOS workflow.
- The workflow loads the thread row from SQLite, resumes the stored ADK session reference, runs the prompt through `Runner.run_async`, and stores the same session reference for the next turn.
- `/telegram/webhook` validates Telegram's secret header, deduplicates update IDs, handles `/start`, `/help`, `/reset`, and `/agent <name>`, then enqueues normal text messages.

## State

- Thread metadata and active ADK session reference: `.vikram/vikram.sqlite3`
- ADK `DatabaseSessionService` event history: `.vikram/adk_sessions.sqlite3`
- DBOS workflow state: `.vikram/dbos.sqlite3`
- Local Compose volume: `vikram-state`
- Production Compose volume: `vikram-state`

## Runtime

Vikram uses Google ADK with Gemini by default. Model configuration is
`VIKRAM_MODEL`; live calls require `GOOGLE_API_KEY`.

The `web_search` tool is an async ADK function tool around Parallel search. Set
`VIKRAM_PARALLEL_API_KEY` or shared `PARALLEL_API_KEY` to enable it.
