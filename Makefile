.PHONY: up tunnel down logs clean

up:
	@python -c "import shutil, pathlib; p=pathlib.Path('.env'); p.exists() or shutil.copy('.env.example', '.env'); print('[SakhiSetu] .env ready')"
	docker compose up --build -d --wait
	@echo ""
	@echo "=== SakhiSetu is running (local) ==="
	@echo "  Backend API Docs:    http://localhost:8000/docs"
	@echo "  Backend Health:      http://localhost:8000/health"
	@echo "  Leader & Member PWA: http://localhost:5173"
	@echo "  Isolated Buyer View: http://localhost:5174"
	@echo "===================================="

tunnel:
	@python -c "import shutil, pathlib; p=pathlib.Path('.env'); p.exists() or shutil.copy('.env.example', '.env'); print('[SakhiSetu] .env ready')"
	docker compose --profile tunnel up --build -d --wait
	@echo ""
	@echo "=== SakhiSetu Cloudflare Tunnel URLs (wait ~5s if empty) ==="
	@docker compose --profile tunnel logs tunnel-leader tunnel-buyer | python -c "import sys,re; txt=sys.stdin.read(); print('\n'.join(sorted(set(re.findall(r'https://[a-z0-9-]+\.trycloudflare\.com', txt)))))"
	@echo "  (Re-run: docker compose --profile tunnel logs tunnel-leader tunnel-buyer | findstr trycloudflare)"
	@echo "============================================================"

down:
	docker compose --profile tunnel down

clean:
	docker compose --profile tunnel down -v --rmi local
