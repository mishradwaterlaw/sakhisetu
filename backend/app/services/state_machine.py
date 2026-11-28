"""Enforced two-type state machine (§2 & §7).

Invariant:
1. EXPLICIT_APPROVAL_REQUIRED transitions CANNOT occur without a persisted Approval row
   with decision='APPROVED'. No timeout, cron, or default can trigger them.
2. TIME_GATED_CONTEST_WINDOW transitions (only PAYOUT_APPROVED -> DISBURSED) require:
   - Prior explicit approval already exists on the entity
   - contest_window_ends_at <= now
   - zero OPEN contests; if any OPEN contest exists, halts into DISPUTED.
"""

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.governance import Approval
from app.models.money import PayoutBatch
from app.models.quality import Contest


class TransitionKind(str, Enum):
    EXPLICIT_APPROVAL_REQUIRED = "EXPLICIT_APPROVAL_REQUIRED"
    TIME_GATED_CONTEST_WINDOW = "TIME_GATED_CONTEST_WINDOW"
    NON_GATED_WORKFLOW = "NON_GATED_WORKFLOW"


@dataclass(frozen=True)
class TransitionSpec:
    entity_type: str
    from_state: str
    to_state: str
    kind: TransitionKind
    allowed_actor_types: tuple[str, ...] = ()


class StateTransitionError(Exception):
    """Raised when a state transition violates §2/§7 invariants."""


# Authoritative transition table — verifiable by code inspection
TRANSITIONS: dict[tuple[str, str, str], TransitionSpec] = {
    # Order lifecycle
    ("order", "DRAFT", "CONFIRMED"): TransitionSpec(
        "order", "DRAFT", "CONFIRMED", TransitionKind.EXPLICIT_APPROVAL_REQUIRED, ("LEADER",)
    ),
    ("order", "CONFIRMED", "COUNTER_OFFER_SENT"): TransitionSpec(
        "order", "CONFIRMED", "COUNTER_OFFER_SENT", TransitionKind.EXPLICIT_APPROVAL_REQUIRED, ("LEADER",)
    ),
    ("order", "COUNTER_OFFER_SENT", "NEGOTIATING"): TransitionSpec(
        "order", "COUNTER_OFFER_SENT", "NEGOTIATING", TransitionKind.NON_GATED_WORKFLOW
    ),
    ("order", "COUNTER_OFFER_SENT", "CONFIRMED"): TransitionSpec(
        "order", "COUNTER_OFFER_SENT", "CONFIRMED", TransitionKind.NON_GATED_WORKFLOW
    ),
    ("order", "NEGOTIATING", "CONFIRMED"): TransitionSpec(
        "order", "NEGOTIATING", "CONFIRMED", TransitionKind.NON_GATED_WORKFLOW
    ),
    ("order", "CONFIRMED", "PRICING_APPROVED"): TransitionSpec(
        "order", "CONFIRMED", "PRICING_APPROVED", TransitionKind.EXPLICIT_APPROVAL_REQUIRED, ("LEADER",)
    ),
    ("order", "PRICING_APPROVED", "ALLOCATION_PROPOSED"): TransitionSpec(
        "order", "PRICING_APPROVED", "ALLOCATION_PROPOSED", TransitionKind.NON_GATED_WORKFLOW
    ),
    ("order", "ALLOCATION_PROPOSED", "ALLOCATION_APPROVED"): TransitionSpec(
        "order",
        "ALLOCATION_PROPOSED",
        "ALLOCATION_APPROVED",
        TransitionKind.EXPLICIT_APPROVAL_REQUIRED,
        ("LEADER",),
    ),
    ("order", "ALLOCATION_APPROVED", "IN_PRODUCTION"): TransitionSpec(
        "order", "ALLOCATION_APPROVED", "IN_PRODUCTION", TransitionKind.NON_GATED_WORKFLOW
    ),
    ("order", "IN_PRODUCTION", "QC_PENDING"): TransitionSpec(
        "order", "IN_PRODUCTION", "QC_PENDING", TransitionKind.NON_GATED_WORKFLOW
    ),
    ("order", "QC_PENDING", "QC_CLEARED"): TransitionSpec(
        "order", "QC_PENDING", "QC_CLEARED", TransitionKind.EXPLICIT_APPROVAL_REQUIRED, ("REVIEW_COMMITTEE", "LEADER")
    ),
    # Blocker / Recovery lifecycle
    ("blocker", "OPEN", "RECOVERY_APPROVED"): TransitionSpec(
        "blocker", "OPEN", "RECOVERY_APPROVED", TransitionKind.EXPLICIT_APPROVAL_REQUIRED, ("LEADER",)
    ),
    ("blocker", "RECOVERY_APPROVED", "RESOLVED"): TransitionSpec(
        "blocker", "RECOVERY_APPROVED", "RESOLVED", TransitionKind.NON_GATED_WORKFLOW
    ),
    # QC Check lifecycle
    ("qc_check", "FLAG", "RESOLVED"): TransitionSpec(
        "qc_check", "FLAG", "RESOLVED", TransitionKind.EXPLICIT_APPROVAL_REQUIRED, ("LEADER", "FEDERATION")
    ),
    # §17b: Quality dispute escalation to neutral Federation reviewer
    ("contest", "OPEN", "FEDERATION_REVIEW"): TransitionSpec(
        "contest", "OPEN", "FEDERATION_REVIEW", TransitionKind.NON_GATED_WORKFLOW
    ),
    ("contest", "FEDERATION_REVIEW", "RESOLVED_UPHELD"): TransitionSpec(
        "contest", "FEDERATION_REVIEW", "RESOLVED_UPHELD", TransitionKind.EXPLICIT_APPROVAL_REQUIRED, ("FEDERATION",)
    ),
    ("contest", "FEDERATION_REVIEW", "RESOLVED_DISMISSED"): TransitionSpec(
        "contest", "FEDERATION_REVIEW", "RESOLVED_DISMISSED", TransitionKind.EXPLICIT_APPROVAL_REQUIRED, ("FEDERATION",)
    ),
    # Payout lifecycle (§7 resolution of §2 tension)
    ("payout_batch", "PAYOUT_PENDING", "PAYOUT_APPROVED"): TransitionSpec(
        "payout_batch",
        "PAYOUT_PENDING",
        "PAYOUT_APPROVED",
        TransitionKind.EXPLICIT_APPROVAL_REQUIRED,
        ("REVIEW_COMMITTEE",),
    ),
    ("payout_batch", "PAYOUT_APPROVED", "DISPUTED"): TransitionSpec(
        "payout_batch", "PAYOUT_APPROVED", "DISPUTED", TransitionKind.NON_GATED_WORKFLOW
    ),
    ("payout_batch", "PAYOUT_APPROVED", "DISBURSED"): TransitionSpec(
        "payout_batch", "PAYOUT_APPROVED", "DISBURSED", TransitionKind.TIME_GATED_CONTEST_WINDOW
    ),
    ("payout_batch", "DISPUTED", "PAYOUT_APPROVED"): TransitionSpec(
        "payout_batch",
        "DISPUTED",
        "PAYOUT_APPROVED",
        TransitionKind.EXPLICIT_APPROVAL_REQUIRED,
        ("LEADER", "FEDERATION", "REVIEW_COMMITTEE"),
    ),
}


def get_transition_spec(entity_type: str, from_state: str, to_state: str) -> TransitionSpec:
    spec = TRANSITIONS.get((entity_type, from_state, to_state))
    if not spec:
        raise StateTransitionError(
            f"Illegal state transition: {entity_type} cannot move from {from_state} to {to_state}"
        )
    return spec


def record_approval_and_transition(
    db: Session,
    *,
    shg_id: str,
    entity_obj: object,
    entity_type: str,
    entity_id: str,
    current_state: str,
    target_state: str,
    actor_type: str,
    actor_id: str,
    reason: str | None = None,
    evidence: dict | None = None,
) -> Approval:
    """Atomically write an Approval record and advance an EXPLICIT_APPROVAL_REQUIRED state."""
    spec = get_transition_spec(entity_type, current_state, target_state)
    if spec.kind != TransitionKind.EXPLICIT_APPROVAL_REQUIRED:
        raise StateTransitionError(
            f"Transition {current_state} -> {target_state} is {spec.kind.value}, not EXPLICIT_APPROVAL_REQUIRED"
        )
    if spec.allowed_actor_types and actor_type not in spec.allowed_actor_types:
        raise StateTransitionError(
            f"Actor type {actor_type} is not permitted for {entity_type} {current_state} -> {target_state}; "
            f"allowed: {spec.allowed_actor_types}"
        )

    approval = Approval(
        shg_id=shg_id,
        entity_type=entity_type,
        entity_id=entity_id,
        transition_name=f"{current_state}->{target_state}",
        actor_type=actor_type,
        actor_id=actor_id,
        decision="APPROVED",
        reason=reason,
        evidence=evidence or {},
    )
    db.add(approval)
    db.flush()

    setattr(entity_obj, "status", target_state)
    db.flush()
    return approval


def verify_explicit_transition_has_approval(
    db: Session,
    *,
    entity_type: str,
    entity_id: str,
    from_state: str,
    to_state: str,
) -> Approval:
    """Guard for any code path attempting to advance an approval-gated state."""
    spec = get_transition_spec(entity_type, from_state, to_state)
    if spec.kind != TransitionKind.EXPLICIT_APPROVAL_REQUIRED:
        raise StateTransitionError("Not an explicit-approval transition")

    approval = db.scalar(
        select(Approval).where(
            Approval.entity_type == entity_type,
            Approval.entity_id == entity_id,
            Approval.transition_name == f"{from_state}->{to_state}",
            Approval.decision == "APPROVED",
        )
    )
    if not approval:
        raise StateTransitionError(
            f"Blocked {entity_type}({entity_id}) {from_state}->{to_state}: "
            "no explicit Approval record exists (§2 invariant)"
        )
    return approval


def evaluate_payout_contest_window(
    db: Session,
    batch: PayoutBatch,
    now: datetime | None = None,
) -> str:
    """Evaluate TIME_GATED_CONTEST_WINDOW for PAYOUT_APPROVED -> DISBURSED.

    - Never creates approval; requires prior PAYOUT_PENDING->PAYOUT_APPROVED Approval row.
    - If any OPEN contest exists, halts and moves batch to DISPUTED.
    - If contest window has not elapsed, remains in PAYOUT_APPROVED.
    - If contest window elapsed with 0 open contests, advances to DISBURSED.
    """
    now = now or datetime.now(timezone.utc)
    if batch.status != "PAYOUT_APPROVED":
        raise StateTransitionError(
            f"Cannot evaluate contest window from status {batch.status}; must be PAYOUT_APPROVED"
        )

    # Verify prior explicit approval exists (either initial or post-dispute)
    prior_approval = db.scalar(
        select(Approval).where(
            Approval.entity_type == "payout_batch",
            Approval.entity_id == batch.id,
            Approval.transition_name.in_(["PAYOUT_PENDING->PAYOUT_APPROVED", "DISPUTED->PAYOUT_APPROVED"]),
            Approval.decision == "APPROVED",
        )
    )
    if not prior_approval:
        raise StateTransitionError(
            "PayoutBatch is in PAYOUT_APPROVED without an Approval record — invariant violation"
        )

    open_contests = db.scalars(
        select(Contest).where(
            Contest.target_type == "PAYOUT_BATCH",
            Contest.target_id == batch.id,
            Contest.status == "OPEN",
        )
    ).all()

    if open_contests:
        batch.status = "DISPUTED"
        db.flush()
        return "DISPUTED"

    if batch.contest_window_ends_at is None:
        return "PAYOUT_APPROVED"

    window_end = batch.contest_window_ends_at
    if window_end.tzinfo is None:
        window_end = window_end.replace(tzinfo=timezone.utc)

    if now < window_end:
        return "PAYOUT_APPROVED"

    batch.status = "DISBURSED"
    batch.disbursed_at = now
    db.flush()
    return "DISBURSED"
