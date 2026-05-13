from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Any, AsyncIterator

from fastapi import FastAPI, Header, HTTPException, Request
from pydantic import BaseModel, Field
from pydantic_ai import Agent

from raman.agent import build_agent
from raman.dbos_gateway import EventDispatcher, launch_dbos, shutdown_dbos
from raman.gateway import InboundMessage, ThreadStore
from raman.logging import configure_logging, get_logger, thread_hash
from raman.observability import init_observability
from raman.settings import RamanSettings
from raman.spec import load_spec
from raman.telegram import TelegramAdapter

logger = get_logger(__name__)


class ChatRequest(BaseModel):
    prompt: str = Field(min_length=1)
    agent: str | None = None


class ChatResponse(BaseModel):
    agent: str
    output: str


class ThreadMessageRequest(BaseModel):
    prompt: str = Field(min_length=1)
    agent: str | None = None


class EnqueueResponse(BaseModel):
    workflow_id: str
    thread_id: str
    status: str


_settings: RamanSettings | None = None
_agents: dict[str, Agent[None, str]] = {}
_store: ThreadStore | None = None
_dispatcher: EventDispatcher | None = None
_telegram_adapter: TelegramAdapter | None = None


def _get_settings() -> RamanSettings:
    global _settings
    if _settings is None:
        _settings = RamanSettings()
    return _settings


def _get_agent(name: str) -> Agent[None, str]:
    if name not in _agents:
        settings = _get_settings()
        spec = load_spec(name, settings.spec_root)
        _agents[name] = build_agent(spec=spec, settings=settings)
    return _agents[name]


def _get_store() -> ThreadStore:
    global _store
    if _store is None:
        _store = ThreadStore(_get_settings().raman_db_path)
    return _store


def _get_dispatcher() -> EventDispatcher:
    global _dispatcher
    if _dispatcher is None:
        _dispatcher = EventDispatcher()
    return _dispatcher


def _get_telegram_adapter() -> TelegramAdapter:
    global _telegram_adapter
    if _telegram_adapter is None:
        _telegram_adapter = TelegramAdapter(
            settings=_get_settings(),
            store=_get_store(),
            enqueue_message=_get_dispatcher().enqueue_message,
        )
    return _telegram_adapter


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = _get_settings()
    configure_logging(settings.log_level)
    init_observability(settings)
    logger.info(
        "api_starting",
        default_agent=settings.default_agent,
        model_provider=settings.model_provider,
        model=settings.dev_model,
        db_path=str(settings.raman_db_path),
    )
    launch_dbos(settings)
    _get_agent(settings.default_agent)
    try:
        yield
    finally:
        logger.info("api_stopping")
        _agents.clear()
        global _store, _dispatcher, _telegram_adapter
        _store = None
        _dispatcher = None
        _telegram_adapter = None
        shutdown_dbos()


app = FastAPI(title="raman", lifespan=lifespan)


@app.get("/healthz")
async def healthz() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/chat", response_model=ChatResponse)
async def chat(req: ChatRequest) -> ChatResponse:
    name = req.agent or _get_settings().default_agent
    try:
        agent = _get_agent(name)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=f"Unknown agent: {name}") from exc

    result = await agent.run(req.prompt)
    return ChatResponse(agent=name, output=str(result.output))


@app.post(
    "/threads/{interface}/{external_thread_id}/messages",
    response_model=EnqueueResponse,
)
async def thread_message(
    interface: str,
    external_thread_id: str,
    req: ThreadMessageRequest,
) -> EnqueueResponse:
    logger.info(
        "thread_message_received",
        interface=interface,
        thread_hash=thread_hash(interface, external_thread_id),
        agent=req.agent,
        prompt_length=len(req.prompt),
    )
    enqueued = await _get_dispatcher().enqueue_message(
        InboundMessage(
            interface=interface,
            external_thread_id=external_thread_id,
            prompt=req.prompt,
            agent_name=req.agent,
            metadata={},
        )
    )
    logger.info(
        "thread_message_enqueued",
        interface=interface,
        thread_hash=thread_hash(interface, external_thread_id),
        workflow_id=enqueued.workflow_id,
        status=enqueued.status,
    )
    return EnqueueResponse(
        workflow_id=enqueued.workflow_id,
        thread_id=f"{interface}:{external_thread_id}",
        status=enqueued.status,
    )


@app.get("/events/{workflow_id}")
async def event_status(workflow_id: str) -> dict[str, Any]:
    return await _get_dispatcher().get_event_status(workflow_id)


@app.post("/telegram/webhook")
async def telegram_webhook(
    request: Request,
    x_telegram_bot_api_secret_token: str | None = Header(default=None),
) -> dict[str, Any]:
    settings = _get_settings()
    if not settings.telegram_webhook_secret:
        logger.warning("telegram_webhook_unconfigured")
        raise HTTPException(
            status_code=503,
            detail="TELEGRAM_WEBHOOK_SECRET is not configured",
        )
    if x_telegram_bot_api_secret_token != settings.telegram_webhook_secret:
        logger.warning("telegram_webhook_secret_rejected")
        raise HTTPException(status_code=403, detail="Invalid Telegram webhook secret")
    update = await request.json()
    result = await _get_telegram_adapter().handle_update(update)
    logger.info(
        "telegram_webhook_processed",
        update_id=update.get("update_id"),
        status=result.status,
        workflow_id=result.workflow_id,
    )
    return {
        "status": result.status,
        "workflow_id": result.workflow_id,
    }


def run() -> None:
    import uvicorn

    uvicorn.run("raman.api:app", host="127.0.0.1", port=8000, reload=False)


if __name__ == "__main__":
    run()
