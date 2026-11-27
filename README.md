# SakhiSetu

## Quickstart

**Prerequisites**: Docker Desktop only (no local Python, Node, or PostgreSQL install required).

```sh
make up
```

Once healthy, you'll see a seeded demo SHG (*Kaveri Mahila Sangha*), 5 members, and a sample `DRAFT` order live across four endpoints:
- **Leader, JanAI Café & Member PWA**: http://localhost:5173
- **Isolated Buyer Portal**: http://localhost:5174
- **Backend API Docs**: http://localhost:8000/docs
- **Backend Healthcheck**: http://localhost:8000/health

---

## Architecture & Design
- System architecture: [ARCHITECTURE.md](ARCHITECTURE.md)
- UI/UX design system & tokens: [DESIGN.md](DESIGN.md)
