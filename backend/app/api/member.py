"""Member self-service & replayable earnings/work record API (§1, §7, §12)."""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import require_member_self
from app.database import get_db
from app.models.governance import CommsLog
from app.models.money import LedgerAccount, LedgerEntry
from app.models.people import Member
from app.models.planning import Task, TaskAssignment
from app.models.quality import QCCheck
from app.services.payout import raise_payout_contest
from app.services.quality import contest_qc_flag

router = APIRouter(prefix="/api/member", tags=["member"])


class ContestIn(BaseModel):
    reason: str


@router.get("/{member_id}/record")
def get_member_own_record(
    member_id: str,
    _caller: str = Depends(require_member_self),
    db: Session = Depends(get_db),
):
    """Every member can view/hear her own work and pay record directly, in her own language (§1)."""
    member = db.get(Member, member_id)
    if not member:
        raise HTTPException(status_code=404, detail="Member not found")

    acct = db.scalar(select(LedgerAccount).where(LedgerAccount.member_id == member_id))
    entries = db.scalars(
        select(LedgerEntry).where(LedgerEntry.member_id == member_id).order_by(LedgerEntry.created_at.desc())
    ).all()
    assignments = db.scalars(
        select(TaskAssignment).where(TaskAssignment.member_id == member_id).order_by(TaskAssignment.created_at.desc())
    ).all()
    qc_notes = db.scalars(
        select(QCCheck).where(QCCheck.member_id == member_id).order_by(QCCheck.created_at.desc())
    ).all()
    replayable_comms = db.scalars(
        select(CommsLog)
        .where(CommsLog.recipient_member_id == member_id, CommsLog.is_replayable.is_(True))
        .order_by(CommsLog.created_at.desc())
    ).all()

    return {
        "member": {
            "id": member.id,
            "name": member.name,
            "preferred_language": member.preferred_language,
            "default_channel": member.default_channel,
        },
        "balance_inr": acct.balance_inr if acct else 0.0,
        "ledger_entries": [
            {
                "id": e.id,
                "payout_batch_id": e.payout_batch_id,
                "amount_inr": e.amount_inr,
                "entry_type": e.entry_type,
                "description": e.description,
                "is_disbursed": e.is_disbursed,
                "created_at": e.created_at.isoformat(),
            }
            for e in entries
        ],
        "assignments": [
            {
                "id": a.id,
                "order_id": a.order_id,
                "step_name": (db.get(Task, a.task_id).step_name if db.get(Task, a.task_id) else "task"),
                "assigned_units": a.assigned_units,
                "completed_units": a.completed_units,
                "passed_units": a.passed_units,
                "status": a.status,
            }
            for a in assignments
        ],
        "private_coaching_notes": [
            {"qc_check_id": q.id, "outcome": q.outcome, "coaching_note": q.private_coaching_note}
            for q in qc_notes
            if q.private_coaching_note
        ],
        "replayable_messages": [
            {
                "id": c.id,
                "category": c.message_category,
                "language": c.language,
                "fact": c.fact_text,
                "action": c.action_text,
                "request": c.request_text,
                "created_at": c.created_at.isoformat(),
            }
            for c in replayable_comms
        ],
    }


@router.post("/{member_id}/payouts/{batch_id}/contest")
def member_contest_payout(
    member_id: str,
    batch_id: str,
    body: ContestIn,
    db: Session = Depends(get_db),
):
    try:
        contest = raise_payout_contest(db, batch_id=batch_id, member_id=member_id, reason=body.reason)
        db.commit()
        return {"contest_id": contest.id, "status": contest.status, "batch_status": "DISPUTED"}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/{member_id}/qc/{qc_check_id}/contest")
def member_contest_qc(
    member_id: str,
    qc_check_id: str,
    body: ContestIn,
    db: Session = Depends(get_db),
):
    try:
        contest = contest_qc_flag(db, qc_check_id=qc_check_id, member_id=member_id, reason=body.reason)
        db.commit()
        return {"contest_id": contest.id, "status": contest.status}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
