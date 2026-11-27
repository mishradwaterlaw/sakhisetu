"""Exotel programmable Voice / DTMF adapter + ExoML builder."""

import xml.etree.ElementTree as ET
import httpx

from app.adapters.channels.base import NormalizedInbound, OutboundChoicePrompt, render_prompt_for_channel
from app.config import get_settings


def parse_exotel_webhook(payload: dict) -> NormalizedInbound:
    """Normalize Exotel Passthru / Gather / Voice-note callback into NormalizedInbound."""
    return NormalizedInbound(
        channel="basic_phone_voice",
        provider_message_id=payload.get("CallSid") or payload.get("call_sid"),
        sender_phone=payload.get("From") or payload.get("sender_phone"),
        raw_text=payload.get("transcript"),
        dtmf_digit=payload.get("digits") or payload.get("dtmf_digit"),
        raw_payload=payload,
    )


def build_exoml_response(prompt: OutboundChoicePrompt, gather_action_url: str = "/api/webhooks/exotel/dtmf") -> str:
    rendered = render_prompt_for_channel(prompt, "basic_phone_voice")
    root = ET.Element("Response")
    if rendered["type"] == "exoml_gather":
        gather = ET.SubElement(root, "Gather", action=gather_action_url, numDigits="1", timeout="10")
        say = ET.SubElement(gather, "Say", language=prompt.language)
        say.text = rendered["spoken_script"]
    else:
        say = ET.SubElement(root, "Say", language=prompt.language)
        say.text = rendered["spoken_script"]
    return ET.tostring(root, encoding="unicode")


async def trigger_exotel_outbound_call(to_phone: str, exoml_url: str) -> dict:
    settings = get_settings()
    if settings.voice_provider == "sandbox" or not settings.exotel_api_key:
        return {"status": "SANDBOX_CALL_QUEUED", "to": to_phone, "exoml_url": exoml_url}

    try:
        url = (
            f"https://api.exotel.com/v1/Accounts/{settings.exotel_account_sid}/Calls/connect.json"
        )
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                url,
                auth=(settings.exotel_api_key, settings.exotel_api_token),
                data={"From": to_phone, "CallerId": settings.exotel_caller_id, "Url": exoml_url},
            )
            resp.raise_for_status()
            return {"status": "CALL_INITIATED", "provider_response": resp.json()}
    except Exception as exc:
        return {"status": "FAILED_RETRYABLE", "error": str(exc)}
