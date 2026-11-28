"""Unified multi-channel webhook endpoints: WhatsApp (Gupshup/Karix), Exotel Voice/DTMF, JanAI Café."""

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.adapters.channels.base import ChoiceOption, OutboundChoicePrompt
from app.adapters.channels.exotel_voice import build_exoml_response, parse_exotel_webhook
from app.adapters.channels.janai_cafe import parse_janai_cafe_submission
from app.adapters.channels.whatsapp_bsp import parse_whatsapp_webhook
from app.adapters.lyzr.orchestrator import run_intake_pipeline
from app.database import get_db

router = APIRouter(prefix="/api/webhooks", tags=["webhooks"])


class WhatsAppWebhookIn(BaseModel):
    shg_id: str
    sender_phone: str | None = None
    text: str | None = None
    audio_base64: str | None = None
    button_id: str | None = None
    message_id: str | None = None
    payload: dict | None = None


class ExotelWebhookIn(BaseModel):
    shg_id: str
    From: str | None = None
    CallSid: str | None = None
    transcript: str | None = None
    digits: str | None = None


class JanAICafeIn(BaseModel):
    shg_id: str
    member_phone: str
    notes_text: str
    operator_id: str = "cafe_op_1"
    member_consented: bool = False
    intent_override: str | None = None
    submission_id: str | None = None


@router.post("/whatsapp")
def whatsapp_inbound(body: WhatsAppWebhookIn, db: Session = Depends(get_db)):
    inbound = parse_whatsapp_webhook(body.model_dump())
    outcome = run_intake_pipeline(db, shg_id=body.shg_id, inbound=inbound)
    db.commit()
    return {
        "trace_id": outcome.trace_id,
        "inbound_message_id": outcome.inbound_message_id,
        "status": outcome.status,
        "order_id": outcome.order_id,
        "clarification_prompt": outcome.clarification_prompt,
        "onboarding_played": outcome.onboarding_played,
    }


@router.post("/exotel")
def exotel_inbound(body: ExotelWebhookIn, db: Session = Depends(get_db)):
    inbound = parse_exotel_webhook(body.model_dump())
    outcome = run_intake_pipeline(db, shg_id=body.shg_id, inbound=inbound)
    db.commit()

    if outcome.status == "UNROUTED":
        prompt = OutboundChoicePrompt(
            fact="We received your call.",
            action="Tell us what you are calling about.",
            request="Choose an option on your keypad.",
            options=[
                ChoiceOption("NEW_ORDER", "New Order", "1"),
                ChoiceOption("BLOCKER_REPORT", "Problem or Blocker", "2"),
                ChoiceOption("FINISHED_WORK", "Finished Work", "3"),
            ],
        )
        return Response(content=build_exoml_response(prompt), media_type="application/xml")

    return {
        "trace_id": outcome.trace_id,
        "inbound_message_id": outcome.inbound_message_id,
        "status": outcome.status,
        "order_id": outcome.order_id,
        "clarification_prompt": outcome.clarification_prompt,
        "onboarding_played": outcome.onboarding_played,
    }


@router.post("/janai-cafe")
def janai_cafe_inbound(body: JanAICafeIn, db: Session = Depends(get_db)):
    try:
        inbound = parse_janai_cafe_submission(body.model_dump())
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    outcome = run_intake_pipeline(db, shg_id=body.shg_id, inbound=inbound)
    db.commit()
    return {
        "trace_id": outcome.trace_id,
        "inbound_message_id": outcome.inbound_message_id,
        "status": outcome.status,
        "order_id": outcome.order_id,
        "clarification_prompt": outcome.clarification_prompt,
        "onboarding_played": outcome.onboarding_played,
    }
