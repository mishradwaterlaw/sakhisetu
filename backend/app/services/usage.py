"""Cost & usage metering service (§9)."""

from datetime import datetime, timezone
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models.governance import UsageMeter


def current_period_ym(now: datetime | None = None) -> str:
    now = now or datetime.now(timezone.utc)
    return now.strftime("%Y-%m")


def record_usage(
    db: Session,
    *,
    shg_id: str,
    resource_type: str,
    provider: str,
    quantity: float,
    unit: str,
    trace_id: str | None = None,
    period_ym: str | None = None,
) -> UsageMeter:
    settings = get_settings()
    cost = 0.0
    if resource_type == "LLM_TOKENS":
        cost = (quantity / 1000.0) * settings.cost_per_llm_1k_tokens_inr
    elif resource_type in ("ASR_MINUTES", "TTS_MINUTES"):
        rate = (
            settings.cost_per_asr_min_bhashini_inr
            if provider == "bhashini"
            else settings.cost_per_asr_min_fallback_inr
        )
        cost = quantity * rate
    elif resource_type == "VOICE_MINUTES":
        cost = quantity * settings.cost_per_voice_min_exotel_inr
    elif resource_type == "WHATSAPP_MSG":
        cost = quantity * settings.cost_per_whatsapp_msg_inr
    elif resource_type == "VISION_CALL":
        cost = quantity * 0.15

    meter = UsageMeter(
        shg_id=shg_id,
        period_ym=period_ym or current_period_ym(),
        resource_type=resource_type,
        provider=provider,
        quantity=quantity,
        unit=unit,
        estimated_cost_inr=round(cost, 4),
        trace_id=trace_id,
    )
    db.add(meter)
    db.flush()
    return meter


def get_shg_monthly_cost_summary(db: Session, shg_id: str, period_ym: str | None = None) -> dict:
    ym = period_ym or current_period_ym()
    rows = db.execute(
        select(
            UsageMeter.resource_type,
            UsageMeter.provider,
            func.sum(UsageMeter.quantity),
            func.sum(UsageMeter.estimated_cost_inr),
        )
        .where(UsageMeter.shg_id == shg_id, UsageMeter.period_ym == ym)
        .group_by(UsageMeter.resource_type, UsageMeter.provider)
    ).all()

    items = [
        {
            "resource_type": r[0],
            "provider": r[1],
            "total_quantity": round(float(r[2] or 0.0), 3),
            "total_cost_inr": round(float(r[3] or 0.0), 4),
        }
        for r in rows
    ]
    total_cost = round(sum(i["total_cost_inr"] for i in items), 2)
    return {"shg_id": shg_id, "period_ym": ym, "total_cost_inr": total_cost, "breakdown": items}
