"""Real Lyzr Agent API client + Pydantic structured output schemas (§4.4, §4.5, §8)."""

import json
from typing import Literal
import httpx
from pydantic import BaseModel, Field

from app.config import get_settings


class RouteIntentSchema(BaseModel):
    intent: Literal["NEW_ORDER", "BLOCKER_REPORT", "FINISHED_WORK", "UNROUTED"]
    confidence: float = Field(ge=0.0, le=1.0)
    reason: str


class ExtractedFieldValue(BaseModel):
    value: str | int | float | None = None
    confidence: float = Field(ge=0.0, le=1.0)
    source_span: str | None = None


class ExtractedOrderSchema(BaseModel):
    product: ExtractedFieldValue
    quantity: ExtractedFieldValue
    offered_price: ExtractedFieldValue
    due_date: ExtractedFieldValue


class PricingAnalysisSchema(BaseModel):
    verdict: Literal["ACCEPT", "COUNTER_OFFER", "DECLINE", "INSUFFICIENT_DATA"]
    recommended_price_inr: float
    rationale: str
    draft_message: str | None = None


class LyzrCallResult(BaseModel):
    trace_id: str
    raw_response: str
    total_tokens: int
    provider: str = "lyzr"


def call_lyzr_agent(
    *,
    agent_id: str,
    user_id: str,
    session_id: str,
    message: str,
) -> LyzrCallResult:
    """Invoke Lyzr Studio / Agent API and return its real trace/run ID and token usage."""
    settings = get_settings()
    if not settings.lyzr_api_key:
        raise RuntimeError("LYZR_API_KEY is not configured")
    if not agent_id:
        raise RuntimeError("Lyzr agent_id is not configured")

    with httpx.Client(timeout=20.0) as client:
        resp = client.post(
            settings.lyzr_agent_api_url,
            headers={"x-api-key": settings.lyzr_api_key, "Content-Type": "application/json"},
            json={
                "user_id": user_id,
                "agent_id": agent_id,
                "session_id": session_id,
                "message": message,
            },
        )
        resp.raise_for_status()
        data = resp.json()

    trace_id = (
        data.get("trace_id")
        or data.get("run_id")
        or data.get("session_id")
        or session_id
    )
    usage = data.get("usage") or {}
    tokens = int(
        usage.get("total_tokens")
        or (usage.get("prompt_tokens", 0) + usage.get("completion_tokens", 0))
        or 0
    )
    return LyzrCallResult(
        trace_id=str(trace_id),
        raw_response=str(data.get("response") or data.get("message") or json.dumps(data)),
        total_tokens=tokens,
    )
