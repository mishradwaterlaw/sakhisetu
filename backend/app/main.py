"""FastAPI application entrypoint."""

from contextlib import asynccontextmanager
from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.api import buyer, conversations, leader, member, webhooks
from app.database import Base, SessionLocal, engine, get_db
from app.seed import seed_demo_data


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Ensure tables + buyer view exist in local/dev environments
    Base.metadata.create_all(bind=engine)
    with engine.begin() as conn:
        conn.execute(text("DROP VIEW IF EXISTS buyer_order_summary_v"))
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
    db = SessionLocal()
    try:
        seed_demo_data(db)
    finally:
        db.close()
    yield


app = FastAPI(title="SakhiSetu API", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(webhooks.router)
app.include_router(leader.router)
app.include_router(conversations.router)
app.include_router(member.router)
app.include_router(buyer.router)


@app.get("/health")
def health():
    return {"status": "ok", "service": "sakhisetu-backend"}


@app.post("/api/bootstrap")
def bootstrap(db: Session = Depends(get_db)):
    return seed_demo_data(db)
