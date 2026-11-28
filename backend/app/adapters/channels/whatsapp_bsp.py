"""India-focused WhatsApp BSP adapter (Gupshup / Karix) + sandbox mode."""

import base64
import httpx
from app.adapters.channels.base import NormalizedInbound, OutboundChoicePrompt, render_prompt_for_channel
from app.config import get_settings


def parse_whatsapp_webhook(payload: dict) -> NormalizedInbound:
    """Normalize Gupshup/Karix/sandbox webhook JSON into NormalizedInbound."""
    audio_b64 = payload.get("audio_base64")
    audio_bytes = base64.b64decode(audio_b64) if audio_b64 else None
    # Support both Gupshup v2 format and simplified sandbox payload
    if "payload" in payload and isinstance(payload["payload"], dict):
        inner = payload["payload"]
        sender = inner.get("sender", {}).get("phone") or inner.get("source") or payload.get("sender_phone")
        msg_type = inner.get("type", "text")
        msg_payload = inner.get("payload", {})
        text = (msg_payload.get("text") if msg_type == "text" else None) or payload.get("text")
        btn_id = (msg_payload.get("id") if msg_type == "button_reply" else None) or payload.get("button_id")
        return NormalizedInbound(
            channel="whatsapp_smartphone",
            provider_message_id=inner.get("id") or payload.get("message_id"),
            sender_phone=sender,
            raw_text=text,
            audio_bytes=audio_bytes,
            button_payload_id=btn_id,
            raw_payload=inner,
        )

    return NormalizedInbound(
        channel="whatsapp_smartphone",
        provider_message_id=payload.get("message_id"),
        sender_phone=payload.get("sender_phone"),
        raw_text=payload.get("text"),
        audio_bytes=audio_bytes,
        button_payload_id=payload.get("button_id"),
        raw_payload=payload,
    )


async def send_whatsapp_prompt(to_phone: str, prompt: OutboundChoicePrompt) -> dict:
    settings = get_settings()
    rendered = render_prompt_for_channel(prompt, "whatsapp_smartphone")

    if settings.whatsapp_provider == "sandbox" or not settings.gupshup_api_key:
        return {"status": "SANDBOX_SENT", "to": to_phone, "rendered": rendered}

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                "https://api.gupshup.io/wa/api/v1/msg",
                headers={"apikey": settings.gupshup_api_key},
                data={
                    "channel": "whatsapp",
                    "source": settings.gupshup_source_number,
                    "destination": to_phone,
                    "src.name": settings.gupshup_app_name,
                    "message": rendered["body"],
                },
            )
            resp.raise_for_status()
            return {"status": "SENT", "provider_response": resp.json(), "rendered": rendered}
    except Exception as exc:
        return {"status": "FAILED_RETRYABLE", "error": str(exc), "rendered": rendered}
