# M8550 Monitor

Local dashboard for the TP-Link M8550 5G mobile router. Polls the router's web UI every 5 seconds and shows current download/upload rates, a 1h/24h/7d history chart, and a connected-clients table with per-client bandwidth.

Two Docker Compose services share a SQLite file: a Python collector that writes, and a Next.js dashboard that reads.

## Requirements

- Docker Desktop
- Connected to the M8550's Wi-Fi (the collector reaches it at `192.168.1.1`)

## Run

```bash
cp .env.example .env
# edit .env, set M8550_PASSWORD
docker compose up --build -d
```

Open `http://localhost:3000`.

Tail logs:

```bash
docker compose logs -f
```

Stop:

```bash
docker compose down
```

## Known data limits

The M8550 doesn't expose per-client RX/TX split — only a combined `total_bytes` counter per MAC. The dashboard shows one combined ↕ bandwidth column for clients. WAN total ↓ / ↑ are split (the router exposes them directly).

The router web UI's username is hard-coded as `user` (not `admin`) — that's a quirk of this firmware. The collector uses it automatically.

## Where data lives

`./data/m8550.db` — SQLite, two tables: `samples` (WAN totals + rates) and `clients` (per-device per-tick). Bind-mounted into both containers; web reads only.

## Off the M8550 Wi-Fi?

The collector marks each tick `online=0` and the dashboard shows "Router offline". Reconnect and it resumes.

## Development

Run components natively for faster iteration:

```bash
# collector
cd collector
M8550_HOST=http://192.168.1.1 M8550_PASSWORD='...' \
  DB_PATH=../data/m8550.db uv run python -m m8550_collector

# web
cd web
DB_PATH=../data/m8550.db pnpm dev
```

## Tests

```bash
cd collector && uv run pytest
cd web && pnpm test
```

## Layout

- `collector/` — Python daemon: router client, poller, SQLite writer
- `web/` — Next.js 15 dashboard
- `data/` — SQLite (gitignored)
- `docs/superpowers/specs/` — design doc
- `docs/superpowers/plans/` — implementation plan
- `docs/recon.md` — endpoint and auth notes (Phase 0)

## Tech stack

Python 3.12, Next.js 15 (App Router) + TypeScript, better-sqlite3, recharts, Tailwind v4, Docker Compose.
