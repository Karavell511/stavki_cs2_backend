# Stream + Betting Backend (Internal)

Production-oriented FastAPI backend for private tournament streams with virtual-currency betting and Telegram-only auth.

## Stack
- Python 3.11, FastAPI (async)
- PostgreSQL + async SQLAlchemy 2.x
- Alembic migrations
- Redis (rate limiting / websocket support)
- JWT sessions
- Docker + docker-compose

## Run locally
```bash
cp .env.example .env
# edit BOT_TOKEN / JWT_SECRET / TELEGRAM_ADMIN_IDS
make up
```

API: `http://localhost:8000`
Docs: `http://localhost:8000/docs`

## DB migration / seed
```bash
make migrate
make seed-admin
```

## Architecture
```
src/
  main.py
  core/
  db/
  models/
  schemas/
  repositories/
  services/
  api/
  websocket/
```

## Core flow examples

### 1) Telegram auth
```bash
curl -X POST http://localhost:8000/auth/telegram \
  -H 'Content-Type: application/json' \
  -d '{
    "id":12345678,
    "username":"alice",
    "first_name":"Alice",
    "auth_date":1739999999,
    "hash":"<telegram_hash>"
  }'
```

### 2) Create stream (admin)
```bash
curl -X POST http://localhost:8000/admin/streams \
  -H "Authorization: Bearer $TOKEN" \
  -H 'Content-Type: application/json' \
  -d '{
    "title":"Quarter Final #1",
    "description":"Bo3",
    "stream_type":"youtube",
    "stream_url":"https://www.youtube.com/embed/xyz",
    "status":"scheduled",
    "start_time":"2026-03-01T10:00:00Z",
    "betting_locked_at":"2026-03-01T09:55:00Z",
    "teams":[{"name":"Team A"},{"name":"Team B"}]
  }'
```

### 3) Admin balance adjust
```bash
curl -X POST http://localhost:8000/admin/users/<user_uuid>/balance-adjust \
  -H "Authorization: Bearer $TOKEN" \
  -H 'Content-Type: application/json' \
  -d '{"amount":500,"reason":"event bonus"}'
```

### 4) Place bet
```bash
curl -X POST http://localhost:8000/bets \
  -H "Authorization: Bearer $TOKEN" \
  -H 'Content-Type: application/json' \
  -d '{"stream_id":"<stream_uuid>","team_id":"<team_uuid>","amount":100}'
```

### 5) Set winner / settle
```bash
curl -X POST http://localhost:8000/admin/streams/<stream_uuid>/set-winner \
  -H "Authorization: Bearer $TOKEN" \
  -H 'Content-Type: application/json' \
  -d '{"team_id":"<winner_team_uuid>"}'
```

### 6) WebSocket chat
Connect:
`ws://localhost:8000/chat/ws/<stream_uuid>?token=<jwt>`

Send payload:
```json
{"message":"gl hf"}
```

## Notes / defaults
- New users are created on valid Telegram auth; only whitelisted users can proceed.
- Users in `TELEGRAM_ADMIN_IDS` become ADMIN on first login and auto-whitelisted.
- Initial wallet for newly authenticated users defaults to `1000` virtual currency.
- Betting is locked at the earlier of `betting_locked_at` or `start_time`.
- One bet per user per stream is enforced by unique constraint + service checks.
- Settlement is transactional and handles no-winner refunds.
