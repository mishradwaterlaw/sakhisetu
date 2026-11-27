#!/usr/bin/env sh
set -e

echo "[SakhiSetu] Checking external service keys (missing keys run in sandbox/mock mode):"
[ -z "$LYZR_API_KEY" ] && echo "  - LYZR_API_KEY missing -> running Lyzr SuperFlow in local structured sandbox mode"
[ -z "$BHASHINI_API_KEY" ] && echo "  - BHASHINI_API_KEY missing -> running Bhashini ASR/TTS in offline sandbox mode"
[ -z "$GUPSHUP_API_KEY" ] && echo "  - GUPSHUP_API_KEY missing -> running WhatsApp BSP in sandbox mode"
[ -z "$EXOTEL_API_KEY" ] && echo "  - EXOTEL_API_KEY missing -> running Exotel Voice/DTMF in sandbox mode"

echo "[SakhiSetu] Running Alembic database migrations..."
alembic upgrade head

echo "[SakhiSetu] Running idempotent demo seed..."
python -c "from app.database import SessionLocal; from app.seed import seed_demo_data; db = SessionLocal(); print('[SakhiSetu] Seed ready:', seed_demo_data(db)); db.close()"

echo "[SakhiSetu] Starting FastAPI server on 0.0.0.0:8000..."
exec uvicorn app.main:app --host 0.0.0.0 --port 8000
