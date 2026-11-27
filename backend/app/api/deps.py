"""FastAPI authentication & RBAC dependencies."""

from dataclasses import dataclass
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.people import Member
from fastapi import Depends, Header, HTTPException, status

from app.security import decode_access_token


@dataclass
class ActorContext:
    actor_id: str
    role: str  # LEADER | MEMBER | BUYER | CAFE_OPERATOR
    shg_id: str | None = None
    party_id: str | None = None


def get_optional_actor(authorization: str | None = Header(default=None)) -> ActorContext | None:
    if not authorization or not authorization.startswith("Bearer "):
        return None
    token = authorization.removeprefix("Bearer ").strip()
    try:
        payload = decode_access_token(token)
        return ActorContext(
            actor_id=payload["sub"],
            role=payload["role"],
            shg_id=payload.get("shg_id"),
            party_id=payload.get("party_id"),
        )
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token") from exc


def require_buyer_actor(authorization: str | None = Header(default=None), x_buyer_party_id: str | None = Header(default=None)) -> ActorContext:
    actor = get_optional_actor(authorization)
    if actor:
        if actor.role != "BUYER":
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Buyer role required")
        return actor
    if x_buyer_party_id:
        return ActorContext(actor_id=x_buyer_party_id, role="BUYER", party_id=x_buyer_party_id)
    raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Buyer authentication required")


def require_member_self(
    member_id: str,
    authorization: str | None = Header(default=None),
    x_member_id: str | None = Header(default=None),
) -> str:
    """Enforce §18 member-to-member privacy boundary at the data-access layer.
    A member can ONLY query her own member_id — never another member's record.
    """
    actor = get_optional_actor(authorization)
    caller_id = actor.actor_id if actor else x_member_id
    if not caller_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Member authentication required (X-Member-Id or Bearer token)")
    if caller_id != member_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Privacy boundary (§18): members cannot access another member's individual record",
        )
    return caller_id


def require_group_leader(
    shg_id: str, actor: ActorContext | None = Depends(get_optional_actor),
    x_leader_id: str | None = Header(default=None), db: Session = Depends(get_db),
) -> Member:
    if actor and (actor.role != "LEADER" or actor.shg_id != shg_id):
        raise HTTPException(status_code=403, detail="Group leader access required")
    leader_id = actor.actor_id if actor else x_leader_id
    if not leader_id:
        raise HTTPException(status_code=401, detail="Leader identity required")
    leader = db.get(Member, leader_id)
    if not leader or leader.role != "leader" or not leader.is_active or leader.shg_id != shg_id:
        raise HTTPException(status_code=403, detail="Group leader access required")
    return leader
