"""Shared auditable random rotation mechanism for QUALITY and PAYOUT (§7).

Design rule:
- Identical seeded pseudo-random policy for both QUALITY and PAYOUT.
- Leader-assigned rotation is structurally excluded to prevent concentration of power.
- Members can opt out ("pass, not available"), which deterministically reshuffles to the next eligible member.
"""

import hashlib
import random
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.people import Member, SHG
from app.models.quality import ReviewRotation


class RotationError(Exception):
    pass


def _compute_seed(shg_id: str, purpose: str, target_entity_id: str, epoch: int, salt: str = "") -> str:
    raw = f"{shg_id}:{purpose}:{target_entity_id}:{epoch}:{salt}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _select_from_pool(pool: list[str], seed_hex: str, count: int) -> list[str]:
    ordered = sorted(pool)  # canonical order before seeded shuffle
    rng = random.Random(int(seed_hex, 16))
    rng.shuffle(ordered)
    return ordered[: min(count, len(ordered))]


def create_review_rotation(
    db: Session,
    *,
    shg_id: str,
    purpose: str,  # QUALITY | PAYOUT
    target_entity_type: str,
    target_entity_id: str,
    committee_size: int = 2,
    exclude_member_ids: set[str] | None = None,
) -> ReviewRotation:
    if purpose not in ("QUALITY", "PAYOUT"):
        raise RotationError(f"Unsupported rotation purpose: {purpose}")

    shg = db.get(SHG, shg_id)
    if not shg:
        raise RotationError(f"SHG {shg_id} not found")

    members = db.scalars(
        select(Member).where(Member.shg_id == shg_id, Member.is_active.is_(True))
    ).all()

    excluded = exclude_member_ids or set()
    eligible = [m.id for m in members if m.id not in excluded]
    if not eligible:
        raise RotationError("No eligible active members for review rotation")

    seed_hex = _compute_seed(shg_id, purpose, target_entity_id, shg.rotation_epoch)
    selected = _select_from_pool(eligible, seed_hex, committee_size)

    rotation = ReviewRotation(
        shg_id=shg_id,
        purpose=purpose,
        target_entity_type=target_entity_type,
        target_entity_id=target_entity_id,
        selection_seed=seed_hex,
        eligible_member_ids=sorted(eligible),
        selected_member_ids=selected,
        opted_out_member_ids=[],
        committee_size=committee_size,
        status="ACTIVE",
    )
    db.add(rotation)
    db.flush()
    return rotation


def opt_out_and_reshuffle(
    db: Session,
    *,
    rotation_id: str,
    member_id: str,
) -> ReviewRotation:
    """Allow a selected member to pass ('not available') and deterministically reshuffle."""
    rotation = db.get(ReviewRotation, rotation_id)
    if not rotation:
        raise RotationError(f"Rotation {rotation_id} not found")
    if member_id not in rotation.selected_member_ids:
        raise RotationError(f"Member {member_id} is not currently on rotation {rotation_id}")

    opted_out = list(rotation.opted_out_member_ids or [])
    if member_id not in opted_out:
        opted_out.append(member_id)

    remaining_pool = [m for m in (rotation.eligible_member_ids or []) if m not in opted_out]
    if not remaining_pool:
        raise RotationError("All eligible members have opted out; cannot fill review committee")

    # Keep non-opted-out selected members, fill remaining slots deterministically from unselected pool
    kept = [m for m in (rotation.selected_member_ids or []) if m != member_id]
    needed = max(0, rotation.committee_size - len(kept))
    candidates = [m for m in remaining_pool if m not in kept]

    reshuffle_seed = _compute_seed(
        rotation.shg_id,
        rotation.purpose,
        rotation.target_entity_id,
        len(opted_out),
        salt=",".join(sorted(opted_out)),
    )
    replacements = _select_from_pool(candidates, reshuffle_seed, needed)

    rotation.opted_out_member_ids = opted_out
    rotation.selected_member_ids = kept + replacements
    rotation.selection_seed = reshuffle_seed
    db.flush()
    return rotation
