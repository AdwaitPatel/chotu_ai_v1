# Merchant Growth AI — Backend Scaffold

## Sarvam speech integration

### Payment follow-up and sales analysis

After a voice bill is saved the assistant asks cash, online, or udhar. Cash
requires confirmation that money was received. Udhar asks for the customer name,
checks existing accounts and outstanding balance, then asks for confirmation.
Unknown or duplicate names require a mobile number; a new account is created only
after confirmation. Credit bills remain unpaid. This version records whole bills,
not partial repayments.

Online uses Paytm's signed `/v3/order/status` API. Configure `PAYTM_MID`,
`PAYTM_MERCHANT_KEY`, and `PAYTM_PRODUCTION` in `.env` (defaults to staging).
The Paytm payment must have been initiated with the bill's `invoice_number` as
its merchant order ID. This feature checks an existing gateway payment; it does
not create a payment link/QR or match unrelated static-QR/UPI transfers.
Missing credentials, pending/failed transactions, signature errors, and amount
mismatches never mark a bill paid. Say `check` to retry or `baad mein` to leave it
pending. Set production mode only with production credentials.

Say `इस हफ्ते की बिक्री बताओ`, `sales for this week`, or `बिजनेस एनालिसिस करो`.
Reports use confirmed/paid bills in calendar periods in IST; cancelled and draft
bills are excluded. Paid-bill totals are not a payment-date cash-flow report.
Old bills have no recorded payment method until explicitly assigned one.

REST endpoints: `POST /api/orders/{id}/payment` (method cash/online/udhar;
cash_received=true for cash, customer_id for udhar),
`POST /api/orders/{id}/payment/verify`, `GET /api/customers/{id}/credit`,
and `GET /api/analytics?period=day|week|month`.

For an Alembic-managed database apply revision `20260919_0002`. For the original
legacy database previously upgraded in this project, run
`python -m scripts.upgrade_payment_schema`. It preserves existing records.
Test with `python -m unittest tests.test_payments_analytics tests.test_payment_database -v`;
database test fixtures are rolled back and Paytm responses are mocked.

The voice page now records microphone audio with MediaRecorder and sends it to
Sarvam Saaras v3. Agent replies are spoken with Bulbul v3. Set SARVAM_API_KEY in
the server .env and restart the API. No login or access token is required.
This is a single-store prototype: dashboard requests reuse the oldest merchant,
or automatically create Prototype Store when the migrated database is empty.
GET /api/merchant returns that store. Auth routes are removed.
Click Start listening, then Stop and send. Recordings stop after 25 seconds.
Use Test Sarvam voice to check playback independently of the merchant agents.

POST /api/voice/transcribe accepts raw audio bytes with an audio/wav,
audio/webm, audio/ogg, audio/mp4, or audio/mpeg Content-Type and returns {"text": "..."}.
POST /api/voice/speak accepts {"text": "Namaste", "language": "hi-IN"} and
returns audio/wav. Both work without authentication or a database connection.
English output uses en-IN; Hindi/Hinglish output uses hi-IN.
STT defaults to Hindi (SARVAM_STT_LANGUAGE=hi-IN) to reduce language switching
on short confirmations. Set en-IN for English or unknown for automatic detection.

Run `python -m unittest tests.test_sarvam -v` for isolated tests, or
`python -m scripts.check_sarvam` for a live short TTS-to-STT provider check.
The live check consumes a small amount of Sarvam quota.
The existing text/agent WebSocket remains a separate dependency: speech checks
do not validate billing, cart persistence, or the agent database setup.

Voice/chat AI assistant for kirana stores. This scaffold implements:

- **Clean architecture**: `api/` (routes) → `agents/` (orchestration) →
  `services/` (business logic) → `repositories/` (data access) → `domain/` (ORM models)
- **Intent Engine** (`app/intent/`): parses Hindi/Hinglish/English utterances
  into structured intents. Ships with an offline rule-based parser (no API
  key needed) plus a pluggable LLM function-calling backend (OpenAI, Groq, or Gemini).
- **Cart Agent** (`app/agents/cart_agent.py`): fully implemented end-to-end —
  add/remove/update/view cart, backed by `CartService` and Postgres, with
  Redis session memory resolving references like "isko" ("this one").
- **Agent Router**: dispatches every other intent (Order, Analytics, GST,
  Growth, Inventory) to stub agents so the API contract is stable while
  those are built out next.

## Quick start

```bash
cp .env.example .env
docker compose up --build
```

Once containers are healthy, seed demo data:

```bash
docker compose exec backend python -m scripts.seed_data
```

This creates a demo customer (id=1) and a small catalog (rice, flour, sugar,
edible oil, salt, lentils).

## Try the demo flow

```bash
# "2 kilo chawal add karo" -> add rice to cart
curl -X POST localhost:8000/api/voice/query \
  -H "Content-Type: application/json" \
  -d '{"customer_id": 1, "text": "2 kilo chawal add karo"}'

# "4 kilo aata bhi" -> add flour
curl -X POST localhost:8000/api/voice/query \
  -H "Content-Type: application/json" \
  -d '{"customer_id": 1, "text": "4 kilo aata add karo"}'

# "Isko 5 kilo kar do" -> resolves "isko" to flour (last product touched)
curl -X POST localhost:8000/api/voice/query \
  -H "Content-Type: application/json" \
  -d '{"customer_id": 1, "text": "Isko 5 kilo kar do"}'

# "Cart dikhao" -> view cart
curl -X POST localhost:8000/api/voice/query \
  -H "Content-Type: application/json" \
  -d '{"customer_id": 1, "text": "Cart dikhao"}'
```

Direct REST access to the same cart logic (no NLU) is available at
`/api/cart/add`, `/api/cart/update`, `/api/cart/remove`, `/api/cart`,
`/api/cart/clear` — useful for the frontend dashboard to bypass voice/text
parsing entirely.

## Switching on a real LLM for the Intent Engine

## Live voice-stream test page

After starting the stack and seeding data, open `http://localhost:8000`.
The included test frontend streams browser STT (Chrome/Edge) transcripts over
WebSocket to `/api/voice/stream`; interim results are echoed immediately and
final results are processed by the merchant agent. Its **Send demo phrase**
button needs no microphone or STT provider and exercises the exact same path.

The WebSocket uses provider-neutral transcript events, so a Sarvam live-STT
client can replace browser STT without changing the backend contract:
`{"type":"transcript","customer_id":1,"text":"...","is_final":true}`.

By default `LLM_PROVIDER=rule_based` in `.env`, so the system works with zero
API keys. To use OpenAI, Groq, or Gemini function calling instead:

```bash
LLM_PROVIDER=openai
OPENAI_API_KEY=sk-...
# or
LLM_PROVIDER=groq
GROQ_API_KEY=gsk_...
# Optional; defaults to llama-3.3-70b-versatile
GROQ_MODEL=llama-3.3-70b-versatile
# or
LLM_PROVIDER=gemini
GEMINI_API_KEY=...
```

The engine automatically falls back to the rule-based parser if the LLM call
fails, so a flaky API never breaks the merchant's flow.

## What's stubbed (next to build)

- **Order Agent**: create/update/cancel/repeat order, invoice generation
- **Product/Inventory Agent**: price/stock lookups, low-stock detection, reorder suggestions
- **Analytics Agent**: daily/weekly/monthly sales, top products, revenue trends
- **GST Agent**: GST summary and reports
- **Growth Agent**: recommendations, demand forecasting, customer insights
- **Voice pipeline**: Sarvam STT/TTS wiring around `/api/voice/query`
- **Frontend**: React + Tailwind + Recharts dashboard
- **n8n workflows**: daily/weekly reports, low-stock alerts, GST reminders

Each new agent should follow the same pattern as `CartAgent`: a service class
with the business logic, an agent class that turns a `ParsedIntent` into an
`AgentResponse`, and a line added to `AgentRouter.route()`.

## Project layout

```
app/
  core/            # config, DB engine, Redis session memory
  domain/          # SQLAlchemy models (products, customers, carts, orders, ...)
  repositories/    # data access layer (repository pattern)
  services/        # business logic layer
  intent/          # Intent Engine: schemas, rule-based parser, LLM parser, engine
  agents/          # Cart Agent (implemented), Agent Router, other agents (stubs)
  api/             # FastAPI routes + request/response schemas
  main.py          # app entrypoint
scripts/
  seed_data.py     # demo data seeding
```
