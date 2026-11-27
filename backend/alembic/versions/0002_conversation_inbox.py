"""Persistent conversations and backfill for existing installations."""

from alembic import op
from sqlalchemy.orm import Session

from app.database import Base
from app.services.conversations import backfill

revision = "0002_conversations"
down_revision = "0001_initial"
branch_labels = None
depends_on = None

tables = ["conversations", "conversation_participants", "conversation_messages", "conversation_orders", "conversation_reads"]


def upgrade():
    bind = op.get_bind()
    for name in tables:
        Base.metadata.tables[name].create(bind, checkfirst=True)
    with Session(bind=bind) as db:
        backfill(db)
        db.commit()


def downgrade():
    for name in reversed(tables):
        Base.metadata.tables[name].drop(op.get_bind(), checkfirst=True)
