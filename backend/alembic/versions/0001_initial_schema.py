"""Initial schema + data-layer buyer_order_summary_v view.

Revision ID: 0001_initial
Revises:
Create Date: 2026-11-27
"""

from alembic import op
from app.database import Base
import app.models  # noqa: F401

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None

BUYER_VIEW_SQL = """
CREATE VIEW buyer_order_summary_v AS
SELECT
    o.id AS order_id,
    o.order_code,
    o.shg_id,
    s.name AS shg_name,
    o.buyer_party_id,
    o.status,
    o.quantity,
    o.due_date,
    o.agreed_price_per_unit_inr,
    o.rubric_disagreement_risk,
    o.created_at,
    o.updated_at,
    COALESCE((SELECT COUNT(*) FROM tasks t WHERE t.order_id = o.id), 0) AS total_tasks,
    COALESCE((SELECT COUNT(*) FROM tasks t WHERE t.order_id = o.id AND t.status = 'COMPLETED'), 0) AS completed_tasks,
    COALESCE((SELECT SUM(q.units_checked) FROM qc_checks q WHERE q.order_id = o.id AND q.outcome = 'PASS'), 0) AS group_qc_passed_units,
    COALESCE((SELECT SUM(q.units_checked) FROM qc_checks q WHERE q.order_id = o.id AND q.outcome IN ('FLAG', 'ESCALATE')), 0) AS group_qc_flagged_units
FROM orders o
JOIN shgs s ON s.id = o.shg_id;
"""


def upgrade() -> None:
    bind = op.get_bind()
    Base.metadata.create_all(bind=bind)
    op.execute("DROP VIEW IF EXISTS buyer_order_summary_v;")
    op.execute(BUYER_VIEW_SQL)


def downgrade() -> None:
    op.execute("DROP VIEW IF EXISTS buyer_order_summary_v;")
    bind = op.get_bind()
    Base.metadata.drop_all(bind=bind)
