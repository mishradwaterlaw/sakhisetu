"""Mandatory ConsentEvent gate for external data & bank-ready payout file release (§8)."""

import csv
import io
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.governance import ConsentEvent
from app.models.money import PayoutBatch
from app.models.people import Member


class ConsentRequiredError(PermissionError):
    """Raised when attempting to export or share group/member data without a persisted ConsentEvent."""


def grant_consent(
    db: Session,
    *,
    shg_id: str,
    granted_by_member_id: str,
    recipient_type: str,  # BANK | BUYER | FEDERATION
    recipient_id: str | None,
    purpose: str,
    scope: dict,
) -> ConsentEvent:
    event = ConsentEvent(
        shg_id=shg_id,
        granted_by_member_id=granted_by_member_id,
        recipient_type=recipient_type,
        recipient_id=recipient_id,
        purpose=purpose,
        scope=scope,
        consented=True,
    )
    db.add(event)
    db.flush()
    return event


def export_bank_payout_csv(
    db: Session,
    *,
    batch_id: str,
    consent_event_id: str | None,
) -> str:
    """Export bank-ready CSV ONLY if a valid ConsentEvent exists for this SHG and batch."""
    batch = db.get(PayoutBatch, batch_id)
    if not batch:
        raise ValueError("Payout batch not found")

    if not consent_event_id:
        raise ConsentRequiredError("Cannot release bank-ready file without a ConsentEvent (§8)")

    consent = db.scalar(
        select(ConsentEvent).where(
            ConsentEvent.id == consent_event_id,
            ConsentEvent.shg_id == batch.shg_id,
            ConsentEvent.recipient_type == "BANK",
            ConsentEvent.consented.is_(True),
        )
    )
    if not consent:
        raise ConsentRequiredError("Valid BANK ConsentEvent not found for this SHG (§8)")

    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["member_name", "bank_account", "ifsc", "amount_inr", "payout_batch_id"])
    for item in batch.breakdown_snapshot or []:
        m = db.get(Member, item["member_id"])
        if not m:
            continue
        writer.writerow(
            [
                m.name,
                m.bank_account_enc or "NOT_ON_FILE",
                m.ifsc_enc or "NOT_ON_FILE",
                f"{item['amount_inr']:.2f}",
                batch.id,
            ]
        )
    return buf.getvalue()


def generate_bank_creditworthiness_summary(
    db: Session,
    *,
    shg_id: str,
    months: int = 6,
) -> dict:
    """Generate group-level creditworthiness summary (§16).
    Never contains individual member names, defect rates, or individual payout amounts.
    """
    from datetime import datetime, timedelta, timezone
    from app.models.intake import Order
    from app.models.people import SHG
    from app.models.quality import QCCheck

    shg = db.get(SHG, shg_id)
    if not shg:
        raise ValueError("SHG not found")

    cutoff = datetime.now(timezone.utc) - timedelta(days=30 * months)
    orders = db.scalars(
        select(Order).where(Order.shg_id == shg_id, Order.created_at >= cutoff)
    ).all()
    completed_orders = [o for o in orders if o.status in ("QC_CLEARED", "DISBURSED")]
    batches = db.scalars(
        select(PayoutBatch).where(PayoutBatch.shg_id == shg_id, PayoutBatch.created_at >= cutoff)
    ).all()
    disbursed_batches = [b for b in batches if b.status == "DISBURSED"]

    qc_rows = db.scalars(
        select(QCCheck).join(Order, Order.id == QCCheck.order_id).where(Order.shg_id == shg_id)
    ).all()
    passed_units = sum(q.units_checked for q in qc_rows if q.outcome == "PASS")
    total_qc_units = sum(q.units_checked for q in qc_rows)
    group_quality_score_pct = round((passed_units / total_qc_units) * 100.0, 1) if total_qc_units > 0 else 100.0

    return {
        "shg_id": shg.id,
        "shg_name": shg.name,
        "village": shg.village,
        "period_months": months,
        "total_orders": len(orders),
        "completed_orders": len(completed_orders),
        "group_quality_score_pct": group_quality_score_pct,
        "total_payout_batches": len(batches),
        "disbursed_payout_batches": len(disbursed_batches),
        "total_group_disbursed_inr": round(sum(b.total_amount_inr for b in disbursed_batches), 2),
        "privacy_guarantee": "Group-level aggregates only; zero individual member identities or payouts included.",
    }


def share_bank_summary_with_group_consent(
    db: Session,
    *,
    shg_id: str,
    consent_event_id: str | None,
    months: int = 6,
) -> dict:
    """External sharing of bank-ready file requires group-approved ConsentEvent (§16)."""
    if not consent_event_id:
        raise ConsentRequiredError("External bank sharing requires a group-level ConsentEvent (§16)")

    consent = db.scalar(
        select(ConsentEvent).where(
            ConsentEvent.id == consent_event_id,
            ConsentEvent.shg_id == shg_id,
            ConsentEvent.recipient_type.in_(["BANK", "FEDERATION"]),
            ConsentEvent.consented.is_(True),
        )
    )
    if not consent or not consent.scope.get("group_committee_approved"):
        raise ConsentRequiredError(
            "ConsentEvent must carry group_committee_approved=True (leader cannot consent unilaterally)"
        )

    summary = generate_bank_creditworthiness_summary(db, shg_id=shg_id, months=months)
    summary["consent_event_id"] = consent.id
    summary["shared_with"] = consent.recipient_type
    return summary
