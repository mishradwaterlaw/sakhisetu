"""JanAI Café assisted-entry adapter (§3)."""

from app.adapters.channels.base import NormalizedInbound


def parse_janai_cafe_submission(payload: dict) -> NormalizedInbound:
    if not payload.get("member_consented", False):
        raise ValueError("JanAI Café assisted entry requires explicit member consent")

    return NormalizedInbound(
        channel="janai_cafe",
        provider_message_id=payload.get("submission_id"),
        sender_phone=payload.get("member_phone"),
        raw_text=payload.get("notes_text"),
        button_payload_id=payload.get("intent_override"),
        operator_id=payload.get("operator_id", "cafe_operator"),
        member_consented=True,
        raw_payload=payload,
    )
