from __future__ import annotations

from datetime import datetime

from pydantic_ai.models import Model
from pydantic_evals import Case, Dataset
from pydantic_evals.evaluators import LLMJudge


def build_dataset(judge_model: Model, agent_name: str) -> Dataset[str, str]:
    now = datetime.now().astimezone()
    today = now.date().isoformat()
    tz = now.tzname() or now.strftime("%z")

    return Dataset[str, str](
        name=f"{agent_name}_smoke",
        cases=[
            Case(
                name="self_identity",
                inputs="What is your name?",
                evaluators=[
                    LLMJudge(
                        rubric=(
                            f"The response identifies the assistant by the name "
                            f"'{agent_name}' (case-insensitive)."
                        ),
                        model=judge_model,
                        include_input=True,
                    ),
                ],
            ),
            Case(
                name="current_date",
                inputs="What is today's date?",
                evaluators=[
                    LLMJudge(
                        rubric=(
                            f"The response states today's date as {today} "
                            f"(any human format). Reject any other date."
                        ),
                        model=judge_model,
                        include_input=True,
                    ),
                ],
            ),
            Case(
                name="current_timezone",
                inputs="What timezone are you operating in?",
                evaluators=[
                    LLMJudge(
                        rubric=(
                            f"The response identifies the timezone as '{tz}' "
                            f"(or an equivalent name/offset)."
                        ),
                        model=judge_model,
                        include_input=True,
                    ),
                ],
            ),
            Case(
                name="web_search_recent_news",
                inputs=(
                    "Find one notable news headline from the past week and "
                    "summarize it in 1-2 sentences. Include the source URL."
                ),
                evaluators=[
                    LLMJudge(
                        rubric=(
                            "The response describes a specific, concrete news "
                            "event (with named people, places, or organizations) "
                            "AND includes at least one http(s) URL as a source. "
                            "Reject generic statements, refusals, or responses "
                            "that hedge with phrases like 'I don't have access "
                            "to real-time data'."
                        ),
                        model=judge_model,
                        include_input=True,
                    ),
                ],
            ),
            Case(
                name="web_search_factual_lookup",
                inputs=(
                    "What is the per-request price of the Parallel.ai web "
                    "search API in basic mode? Cite the source URL."
                ),
                evaluators=[
                    LLMJudge(
                        rubric=(
                            "The response states a specific dollar amount per "
                            "request or per 1000 requests (e.g. '$0.005' or "
                            "'$0.50/1k') AND includes a parallel.ai URL. "
                            "Reject refusals or responses that omit either the "
                            "price or the URL."
                        ),
                        model=judge_model,
                        include_input=True,
                    ),
                ],
            ),
        ],
    )
