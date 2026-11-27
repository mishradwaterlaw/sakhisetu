"""Channel normalization & fixed-grammar prompt rendering (§3, §12)."""

from dataclasses import dataclass, field


@dataclass
class ChoiceOption:
    id: str
    label: str
    dtmf_digit: str


@dataclass
class OutboundChoicePrompt:
    """Every member prompt follows Fact -> Action -> Request."""

    fact: str
    action: str
    request: str
    language: str = "kn"
    options: list[ChoiceOption] = field(default_factory=list)


@dataclass
class NormalizedInbound:
    channel: str  # whatsapp_smartphone | basic_phone_voice | janai_cafe
    provider_message_id: str | None
    sender_phone: str | None
    raw_text: str | None = None
    audio_bytes: bytes | None = None
    audio_mime: str | None = None
    image_bytes: bytes | None = None
    image_mime: str | None = None
    dtmf_digit: str | None = None
    button_payload_id: str | None = None
    operator_id: str | None = None
    member_consented: bool = True
    raw_payload: dict = field(default_factory=dict)


def render_prompt_for_channel(prompt: OutboundChoicePrompt, channel: str) -> dict:
    """Render the exact same underlying decision appropriately per channel (§3).
    Never surfaces DTMF keypress instructions on WhatsApp; never surfaces tappable buttons on voice.
    """
    base_text = f"{prompt.fact}\n{prompt.action}\n{prompt.request}"

    if channel == "whatsapp_smartphone":
        if prompt.options:
            return {
                "channel": "whatsapp_smartphone",
                "type": "interactive_buttons",
                "body": base_text,
                "buttons": [{"id": o.id, "title": o.label[:20]} for o in prompt.options[:3]],
            }
        return {"channel": "whatsapp_smartphone", "type": "text", "body": base_text}

    if channel == "basic_phone_voice":
        spoken_options = " ".join(f"Press {o.dtmf_digit} for {o.label}." for o in prompt.options)
        spoken_script = f"{prompt.fact}. {prompt.action}. {prompt.request}. {spoken_options}".strip()
        return {
            "channel": "basic_phone_voice",
            "type": "exoml_gather" if prompt.options else "exoml_say",
            "spoken_script": spoken_script,
            "dtmf_map": {o.dtmf_digit: o.id for o in prompt.options},
        }

    # janai_cafe
    return {
        "channel": "janai_cafe",
        "type": "operator_card",
        "fact": prompt.fact,
        "action": prompt.action,
        "request": prompt.request,
        "options": [{"id": o.id, "label": o.label} for o in prompt.options],
    }
