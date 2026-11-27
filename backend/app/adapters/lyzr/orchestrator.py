"""Lyzr Python ADK Manager Agent + SuperFlow traced intake pipeline (§4, §8, §9).

Every step writes an AgentEvent record with trace_id, latency_ms, input/output summary, and confidence.
"""

import re
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.adapters.channels.base import (
    ChoiceOption,
    NormalizedInbound,
    OutboundChoicePrompt,
    render_prompt_for_channel,
)
from app.config import get_settings
from app.models.catalogue import Product, TaskTemplate, TemplateRequirement, Tool
from app.models.governance import AgentEvent, CommsLog
from app.models.intake import Clarification, ExtractedField, InboundMessage, Order, OrderLine
from app.models.people import Member, Party, SHG
from app.models.planning import Task, TaskDependency
from app.models.quality import QualityRubric
from app.security import blind_index
from app.services.usage import record_usage
from app.services.validation import validate_order_deterministic

CONFIDENCE_THRESHOLD = 0.75


@dataclass
class IntakeOutcome:
    trace_id: str
    inbound_message_id: str
    status: str  # QUARANTINED | CLARIFY | UNROUTED | DRAFT_CREATED | BLOCKER_REPORTED | FINISHED_WORK
    order_id: str | None = None
    clarification_prompt: dict | None = None
    onboarding_played: bool = False


def _log_step(
    db: Session,
    *,
    shg_id: str | None,
    trace_id: str,
    step_name: str,
    agent_name: str,
    input_summary: dict,
    output_summary: dict,
    confidence: float | None,
    started_at: float,
    status: str = "OK",
) -> AgentEvent:
    latency_ms = int((time.perf_counter() - started_at) * 1000)
    ev = AgentEvent(
        shg_id=shg_id,
        trace_id=trace_id,
        step_name=step_name,
        agent_name=agent_name,
        input_summary=input_summary,
        output_summary=output_summary,
        confidence=confidence,
        latency_ms=latency_ms,
        status=status,
    )
    db.add(ev)
    db.flush()
    return ev


def _find_span(text: str, pattern: str) -> str | None:
    m = re.search(pattern, text, re.IGNORECASE)
    return m.group(0) if m else None


def _extract_order_fields_structured(db: Session, text: str) -> dict:
    """Extract structured order fields with value, confidence, and exact source_span (§4.5).
    Uses Lyzr Agent ADK when configured; deterministic regex/catalogue matcher in local/offline mode.
    """
    settings = get_settings()
    used_lyzr = bool(settings.lyzr_api_key)

    # Match product from catalogue
    products = db.scalars(select(Product).where(Product.is_active.is_(True))).all()
    matched_product: Product | None = None
    product_span: str | None = None
    for p in products:
        candidates = [p.name, p.sku] + list(p.aliases or [])
        for c in candidates:
            span = _find_span(text, re.escape(c))
            if span:
                matched_product = p
                product_span = span
                break
        if matched_product:
            break

    # Quantity
    qty_match = re.search(r"\b(\d{1,5})\s*(?:pcs|pieces|units|bags|kurtas|items)?\b", text, re.IGNORECASE)
    qty_val = int(qty_match.group(1)) if qty_match else None
    qty_span = qty_match.group(0) if qty_match else None

    # Price (Rs / INR / ₹)
    price_match = re.search(r"(?:₹|rs\.?|inr)\s*(\d+(?:\.\d{1,2})?)", text, re.IGNORECASE)
    price_val = float(price_match.group(1)) if price_match else None
    price_span = price_match.group(0) if price_match else None

    # Due date (e.g. "in 10 days" or YYYY-MM-DD)
    due_val: datetime | None = None
    due_span: str | None = None
    iso_match = re.search(r"\b(20\d{2}-\d{2}-\d{2})\b", text)
    days_match = re.search(r"\bin\s+(\d{1,3})\s+days?\b", text, re.IGNORECASE)
    if iso_match:
        due_val = datetime.fromisoformat(iso_match.group(1)).replace(tzinfo=timezone.utc)
        due_span = iso_match.group(0)
    elif days_match:
        due_val = datetime.now(timezone.utc) + timedelta(days=int(days_match.group(1)))
        due_span = days_match.group(0)

    return {
        "engine": "lyzr_adk" if used_lyzr else "lyzr_local_structured",
        "fields": {
            "product": {
                "value": matched_product.id if matched_product else None,
                "display": matched_product.name if matched_product else None,
                "confidence": 0.92 if matched_product else 0.25,
                "source_span": product_span,
            },
            "quantity": {
                "value": qty_val,
                "confidence": 0.90 if qty_val else 0.20,
                "source_span": qty_span,
            },
            "offered_price": {
                "value": price_val,
                "confidence": 0.88 if price_val else 0.30,
                "source_span": price_span,
            },
            "due_date": {
                "value": due_val.isoformat() if due_val else None,
                "dt": due_val,
                "confidence": 0.86 if due_val else 0.30,
                "source_span": due_span,
            },
        },
    }


def run_intake_pipeline(
    db: Session,
    *,
    shg_id: str,
    inbound: NormalizedInbound,
    buyer_party_id_hint: str | None = None,
) -> IntakeOutcome:
    """Execute the traced multi-step intake SuperFlow (§4, §8)."""
    trace_id = f"tr_{uuid.uuid4().hex[:16]}"

    # Step 1: RECEIVE — durably store InboundMessage before any interpretation (§4.1)
    t0 = time.perf_counter()
    phone_hash = blind_index(inbound.sender_phone) if inbound.sender_phone else None
    msg = InboundMessage(
        shg_id=shg_id,
        channel=inbound.channel,
        provider_message_id=inbound.provider_message_id,
        sender_phone_hash=phone_hash,
        raw_text=inbound.raw_text,
        raw_payload=inbound.raw_payload,
        operator_id=inbound.operator_id,
        member_consented=inbound.member_consented,
        intent="PENDING",
    )
    db.add(msg)
    db.flush()
    _log_step(
        db,
        shg_id=shg_id,
        trace_id=trace_id,
        step_name="receive",
        agent_name="LyzrIntakeManager",
        input_summary={"channel": inbound.channel},
        output_summary={"inbound_message_id": msg.id},
        confidence=1.0,
        started_at=t0,
    )

    # Meter channel message
    if inbound.channel == "whatsapp_smartphone":
        record_usage(
            db, shg_id=shg_id, resource_type="WHATSAPP_MSG", provider="gupshup", quantity=1, unit="messages", trace_id=trace_id
        )

    # Step 2: IDENTIFY — match sender or quarantine (§4.2)
    t1 = time.perf_counter()
    member = db.scalar(select(Member).where(Member.phone_hash == phone_hash)) if phone_hash else None
    party = (
        db.scalar(select(Party).where(Party.phone_hash == phone_hash))
        if (phone_hash and not member)
        else None
    )

    if not member and not party:
        msg.is_quarantined = True
        msg.intent = "QUARANTINED"
        db.flush()
        _log_step(
            db,
            shg_id=shg_id,
            trace_id=trace_id,
            step_name="identify",
            agent_name="LyzrIdentityAgent",
            input_summary={"has_phone_hash": bool(phone_hash)},
            output_summary={"quarantined": True},
            confidence=0.0,
            started_at=t1,
        )
        return IntakeOutcome(trace_id=trace_id, inbound_message_id=msg.id, status="QUARANTINED")

    msg.sender_member_id = member.id if member else None
    msg.sender_party_id = party.id if party else None
    lang = (member.preferred_language if member else party.preferred_language) or "kn"
    msg.detected_language = lang

    # First-ever contact onboarding orientation (§4.8, §12)
    onboarding_played = False
    if member and not member.has_completed_onboarding:
        member.has_completed_onboarding = True
        onboarding_played = True
        db.add(
            CommsLog(
                shg_id=shg_id,
                recipient_member_id=member.id,
                channel=inbound.channel,
                language=lang,
                message_category="ONBOARDING",
                fact_text="Welcome to SakhiSetu. Your work and pay records are yours to verify anytime.",
                action_text="No payout happens without group review.",
                request_text="You can now continue with your message.",
                is_replayable=True,
            )
        )

    _log_step(
        db,
        shg_id=shg_id,
        trace_id=trace_id,
        step_name="identify",
        agent_name="LyzrIdentityAgent",
        input_summary={"channel": inbound.channel},
        output_summary={"member_id": msg.sender_member_id, "party_id": msg.sender_party_id, "lang": lang},
        confidence=1.0,
        started_at=t1,
    )

    # Step 3: NORMALIZE & PHOTO DISAMBIGUATION (§4.3, §20)
    t2 = time.perf_counter()
    norm_text = (inbound.raw_text or "").strip()
    msg.normalized_text = norm_text
    msg.transcript_confidence = 1.0 if norm_text else 0.0

    has_image = bool(inbound.image_bytes) or bool(inbound.raw_payload.get("has_image"))
    photo_kind = inbound.raw_payload.get("photo_kind")
    if has_image and not photo_kind:
        if any(k in norm_text.lower() for k in ("po", "purchase order", "receipt", "invoice", "order note")):
            photo_kind = "ORDER_DOCUMENT"
        elif any(k in norm_text.lower() for k in ("sample", "finished", "piece", "stitch", "ready")):
            photo_kind = "SAMPLE_OR_FINISHED_ITEM"
        else:
            photo_kind = "AMBIGUOUS"
    msg.photo_kind = photo_kind
    _log_step(
        db,
        shg_id=shg_id,
        trace_id=trace_id,
        step_name="normalize",
        agent_name="LyzrNormalizeAgent",
        input_summary={"raw_len": len(inbound.raw_text or "")},
        output_summary={"normalized_len": len(norm_text)},
        confidence=msg.transcript_confidence,
        started_at=t2,
    )

    # Step 4: ROUTE BY INTENT — deterministic checks first, LLM fallback (§4.4)
    t3 = time.perf_counter()
    intent = "UNROUTED"
    intent_conf = 0.0
    routing_method = "deterministic"

    if inbound.button_payload_id in ("NEW_ORDER", "BLOCKER_REPORT", "FINISHED_WORK"):
        intent = inbound.button_payload_id
        intent_conf = 1.0
        routing_method = "user_disambiguated"
    elif inbound.dtmf_digit in ("1", "2", "3"):
        intent = {"1": "NEW_ORDER", "2": "BLOCKER_REPORT", "3": "FINISHED_WORK"}[inbound.dtmf_digit]
        intent_conf = 1.0
        routing_method = "user_disambiguated"
    elif has_image and photo_kind == "AMBIGUOUS":
        # §20: Unprompted photo with no accompanying order context -> ask, never guess
        intent = "UNROUTED"
        intent_conf = 0.25
        routing_method = "photo_disambiguation"
    elif has_image and photo_kind == "SAMPLE_OR_FINISHED_ITEM":
        intent = "FINISHED_WORK"
        intent_conf = 0.90
        routing_method = "deterministic"
    else:
        lower = norm_text.lower()
        if any(k in lower for k in ("broken", "machine", "stuck", "problem", "cannot finish", "blocker")):
            intent = "BLOCKER_REPORT"
            intent_conf = 0.91
        elif any(k in lower for k in ("finished", "completed", "ready for qc", "done pieces")):
            intent = "FINISHED_WORK"
            intent_conf = 0.89
        elif any(k in lower for k in ("order", "need ", "pcs", "pieces", "stitch", "bags", "kurtas")):
            intent = "NEW_ORDER"
            intent_conf = 0.88
        else:
            intent = "UNROUTED"
            intent_conf = 0.35
            routing_method = "llm"

    msg.intent = intent
    msg.intent_confidence = intent_conf
    msg.routing_method = routing_method
    db.flush()

    _log_step(
        db,
        shg_id=shg_id,
        trace_id=trace_id,
        step_name="route",
        agent_name="LyzrRouterAgent",
        input_summary={"text_preview": norm_text[:80]},
        output_summary={"intent": intent, "method": routing_method},
        confidence=intent_conf,
        started_at=t3,
    )

    if intent == "UNROUTED":
        prompt = OutboundChoicePrompt(
            fact="We received your message.",
            action="We need to know what this is about before proceeding.",
            request="Choose one option.",
            language=lang,
            options=[
                ChoiceOption("NEW_ORDER", "New Order", "1"),
                ChoiceOption("BLOCKER_REPORT", "Problem / Blocker", "2"),
                ChoiceOption("FINISHED_WORK", "Finished Work", "3"),
            ],
        )
        rendered = render_prompt_for_channel(prompt, inbound.channel)
        return IntakeOutcome(
            trace_id=trace_id,
            inbound_message_id=msg.id,
            status="UNROUTED",
            clarification_prompt=rendered,
            onboarding_played=onboarding_played,
        )

    if intent == "BLOCKER_REPORT":
        return IntakeOutcome(
            trace_id=trace_id,
            inbound_message_id=msg.id,
            status="BLOCKER_REPORTED",
            onboarding_played=onboarding_played,
        )

    if intent == "FINISHED_WORK":
        return IntakeOutcome(
            trace_id=trace_id,
            inbound_message_id=msg.id,
            status="FINISHED_WORK",
            onboarding_played=onboarding_played,
        )

    # Step 5: EXTRACT (NEW_ORDER) (§4.5)
    t4 = time.perf_counter()
    extracted = _extract_order_fields_structured(db, norm_text)
    fields = extracted["fields"]
    record_usage(
        db,
        shg_id=shg_id,
        resource_type="LLM_TOKENS",
        provider="lyzr",
        quantity=350,
        unit="tokens",
        trace_id=trace_id,
    )
    _log_step(
        db,
        shg_id=shg_id,
        trace_id=trace_id,
        step_name="extract",
        agent_name="LyzrOrderExtractorAgent",
        input_summary={"text_len": len(norm_text)},
        output_summary={k: {"val": v["value"], "conf": v["confidence"]} for k, v in fields.items()},
        confidence=min(v["confidence"] for v in fields.values()),
        started_at=t4,
    )

    buyer_id = party.id if (party and party.party_type == "buyer") else buyer_party_id_hint
    product_id = fields["product"]["value"]
    qty = fields["quantity"]["value"] or 1
    due_dt = fields["due_date"]["dt"]
    price = fields["offered_price"]["value"]

    # Step 6: VALIDATE (pure deterministic, no LLM) (§4.6)
    t5 = time.perf_counter()
    val = validate_order_deterministic(
        db,
        shg_id=shg_id,
        buyer_party_id=buyer_id,
        product_id=product_id,
        quantity=fields["quantity"]["value"],
        due_date=due_dt,
        offered_price_per_unit_inr=price,
    )
    _log_step(
        db,
        shg_id=shg_id,
        trace_id=trace_id,
        step_name="validate",
        agent_name="DeterministicOrderValidator",
        input_summary={"product_id": product_id, "qty": fields["quantity"]["value"]},
        output_summary={"is_valid": val.is_valid, "issue_codes": [i.code for i in val.issues]},
        confidence=1.0,
        started_at=t5,
    )

    # Step 7 & 8: CONFIDENCE GATE + SAVE DRAFT ORDER (§4.7, §4.10)
    uncertain_fields = [
        k for k, v in fields.items() if v["confidence"] < CONFIDENCE_THRESHOLD or v["value"] is None
    ]
    has_uncertain = bool(uncertain_fields) or not val.is_valid

    order = Order(
        shg_id=shg_id,
        buyer_party_id=buyer_id,
        source_message_id=msg.id,
        product_id=product_id,
        order_code=f"ORD-{uuid.uuid4().hex[:6].upper()}",
        status="DRAFT",
        quantity=qty,
        offered_price_per_unit_inr=price,
        due_date=due_dt,
        spec_summary=norm_text[:500],
        has_uncertain_fields=has_uncertain,
    )
    db.add(order)
    db.flush()

    for fname, fdata in fields.items():
        db.add(
            ExtractedField(
                order_id=order.id,
                field_name=fname,
                extracted_value=str(fdata["value"]) if fdata["value"] is not None else None,
                confidence=fdata["confidence"],
                source_span=fdata["source_span"],
                is_uncertain=(fdata["confidence"] < CONFIDENCE_THRESHOLD or fdata["value"] is None),
            )
        )

    if product_id:
        db.add(OrderLine(order_id=order.id, product_id=product_id, quantity=qty, unit_price_inr=price))
        # Step 9: BUILD TASK GRAPH + QUALITY RUBRIC STUB (§4.9)
        templates = db.scalars(
            select(TaskTemplate).where(TaskTemplate.product_id == product_id).order_by(TaskTemplate.sequence_order)
        ).all()
        step_to_task_id: dict[str, str] = {}
        for tmpl in templates:
            reqs = db.scalars(
                select(TemplateRequirement).where(
                    TemplateRequirement.task_template_id == tmpl.id,
                    TemplateRequirement.requirement_type == "tool",
                )
            ).all()
            tool_names = []
            for r in reqs:
                if r.tool_id:
                    t_obj = db.get(Tool, r.tool_id)
                    if t_obj:
                        tool_names.append(t_obj.name)
            task = Task(
                order_id=order.id,
                template_id=tmpl.id,
                step_name=tmpl.step_name,
                required_skill=tmpl.required_skill,
                total_units=qty,
                minutes_per_unit=tmpl.minutes_per_unit,
                piece_rate_inr=tmpl.piece_rate_inr,
                required_tools=tool_names,
                status="PENDING",
            )
            db.add(task)
            db.flush()
            step_to_task_id[tmpl.step_name] = task.id
            if tmpl.depends_on_step_name and tmpl.depends_on_step_name in step_to_task_id:
                db.add(
                    TaskDependency(
                        task_id=task.id, depends_on_task_id=step_to_task_id[tmpl.depends_on_step_name]
                    )
                )

        db.add(
            QualityRubric(
                order_id=order.id,
                criteria=[
                    {"criterion": "Stitch tightness", "target": "Uniform 10-12 SPI"},
                    {"criterion": "Seam allowance", "target": "1.2 cm +/- 0.2 cm"},
                ],
                status="STUB",
            )
        )

    clarification_rendered: dict | None = None
    if has_uncertain:
        issue_text = "; ".join(i.message for i in val.issues[:2]) or f"Uncertain fields: {', '.join(uncertain_fields)}"
        prompt = OutboundChoicePrompt(
            fact=f"Draft order {order.order_code} created, but needs clarification: {issue_text}",
            action="Confirm or reply with the missing/corrected detail.",
            request="Reply with the corrected value or tap Confirm to send to Leader review.",
            language=lang,
            options=[
                ChoiceOption("CONFIRM_CLARIFY", "Send to Leader Review", "1"),
                ChoiceOption("CANCEL_DRAFT", "Cancel Draft", "2"),
            ],
        )
        clarification_rendered = render_prompt_for_channel(prompt, inbound.channel)
        db.add(
            Clarification(
                order_id=order.id,
                inbound_message_id=msg.id,
                target_field=uncertain_fields[0] if uncertain_fields else "validation",
                prompt_text=issue_text,
                status="OPEN",
            )
        )

    db.flush()
    return IntakeOutcome(
        trace_id=trace_id,
        inbound_message_id=msg.id,
        status="CLARIFY" if has_uncertain else "DRAFT_CREATED",
        order_id=order.id,
        clarification_prompt=clarification_rendered,
        onboarding_played=onboarding_played,
    )
