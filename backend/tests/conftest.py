"""Pytest fixtures with isolated SQLite test DB + buyer_order_summary_v view."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import app
from app.seed import seed_demo_data


@pytest.fixture()
def db_session():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    with engine.begin() as conn:
        conn.execute(
            text(
                """
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
                JOIN shgs s ON s.id = o.shg_id
                """
            )
        )
    TestingSession = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    session = TestingSession()
    seed_demo_data(session)
    try:
        yield session
    finally:
        session.close()


@pytest.fixture()
def client(db_session):
    def _override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = _override_get_db
    # Do not enter lifespan(app) in unit tests so TestClient uses the in-memory SQLite db_session
    # instead of attempting to connect to the default PostgreSQL host.
    yield TestClient(app)
    app.dependency_overrides.clear()
