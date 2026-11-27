.PHONY: up down logs clean

up:
	@python -c "import shutil, pathlib; p=pathlib.Path('.env'); p.exists() or shutil.copy('.env.example', '.env'); print('[SakhiSetu] .env ready')"
	docker compose up --build -d
	@python -c "import time, urllib.request; \
	[None for _ in range(30) if (lambda: (urllib.request.urlopen('http://localhost:8000/health').status == 200) if not print('', end='') else False)() or time.sleep(2)]" 2>nul || true
	@echo ""
	@echo "=== SakhiSetu is running ==="
	@echo "  Backend API Docs:   http://localhost:8000/docs"
	@echo "  Backend Health:     http://localhost:8000/health"
	@echo "  Leader & Member PWA: http://localhost:5173"
	@echo "  Isolated Buyer View: http://localhost:5174"
	@echo "============================"

down:
	docker compose down

clean:
	docker compose down -v --rmi local
