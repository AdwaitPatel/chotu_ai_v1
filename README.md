# Chotu AI

Chotu AI is a voice-first commerce assistant and operations dashboard for small
kirana stores. It combines a FastAPI backend with a React dashboard, PostgreSQL,
Redis, intent parsing, cart management, payments, analytics, and optional
Sarvam speech services.

## Project structure

- `backend/` - FastAPI API, agents, services, database models, and migrations
- `frontend/` - React + Vite merchant dashboard

## Run locally

Live frontend: https://chotuai-rfsk0qxoy-adwaitpatels-projects.vercel.app/

### Backend

Requirements: Docker Desktop.

```bash
cd backend
cp .env.example .env
docker compose up --build
```

In another terminal, seed demo data:

```bash
cd backend
docker compose exec backend python -m scripts.seed_data
```

The API is available at `http://localhost:8000` and its Swagger UI at
`http://localhost:8000/docs`.

### Frontend

Requirements: Node.js and npm.

```bash
cd frontend
npm install
npm run dev
```

Open the local Vite URL shown in the terminal. During local development, API
requests are proxied to the backend at `http://localhost:8000`.

## Configuration

Copy `backend/.env.example` to `backend/.env`. The default configuration uses
the offline rule-based intent parser. Add provider credentials only when using
LLM, Sarvam voice, or Paytm payment integrations.

## Tests

```bash
cd backend
python -m unittest discover -s tests -v
```
