# M8550 Monitor — Design

**Date:** 2026-04-28
**Status:** Approved (brainstorm)

## Goal

Local dashboard that polls a TP-Link M8550 5G mobile router and shows:

- Current download / upload rate.
- Connected clients with their per-client current bandwidth.
- Historical D/U chart over selectable ranges (1h / 24h / 7d).

Runs on the user's Mac/PC (whichever machine is on the M8550's Wi-Fi). Single user, single device, local network only. No cloud, no Home Assistant, no auth on the dashboard.

## Constraints and assumptions

- The M8550 has no official API. We talk to its local web UI at `http://192.168.1.1`. Endpoints and auth flow must be reverse-engineered from a browser session before serious code is written.
- The user must be on the M8550's Wi-Fi for the collector to reach it. Off-network = no data; the dashboard must show this clearly rather than appearing broken.
- Poll interval: 5 seconds.
- Run as containers via Docker Compose by default. Native run is supported for iteration.

## Architecture

Two cooperating processes, sharing a single SQLite file.

```
┌──────────────────────────┐      ┌──────────────────────────┐
│ collector  (Python)      │      │ web  (Next.js 15)        │
│                          │      │                          │
│  router client (login,   │      │  app router pages        │
│  fetch endpoints)        │      │  api routes              │
│        │                 │      │        │                 │
│        ▼ every 5s        │      │        ▼                 │
│  poller → store          │      │  better-sqlite3 (RO)     │
└──────────┬───────────────┘      └──────────┬───────────────┘
           │ writes                          │ reads
           ▼                                 ▼
        ┌─────────────────────────────────────────┐
        │ data/m8550.db  (SQLite, WAL mode)       │
        └─────────────────────────────────────────┘

Collector ⇄ 192.168.1.1     Browser ⇄ http://localhost:3000
```

Collector writes; web is read-only. WAL mode keeps the writer and reader from blocking each other.

## Project layout

```
home-assistant/
├── compose.yaml
├── .env.example
├── .gitignore
├── README.md
├── data/                       # SQLite lives here, bind-mounted
├── collector/
│   ├── Dockerfile
│   ├── pyproject.toml          # uv
│   ├── src/m8550_collector/
│   │   ├── __init__.py
│   │   ├── __main__.py         # entry point
│   │   ├── router.py           # M8550 client (login, fetch)
│   │   ├── poller.py           # 5s loop, rate calc
│   │   └── store.py            # SQLite writes
│   └── tests/
├── web/
│   ├── Dockerfile              # multi-stage: deps → build → runtime
│   ├── package.json
│   ├── app/
│   │   ├── layout.tsx
│   │   ├── page.tsx            # dashboard
│   │   └── api/
│   │       ├── current/route.ts
│   │       └── history/route.ts
│   ├── components/
│   │   ├── rate-card.tsx
│   │   ├── traffic-chart.tsx
│   │   └── clients-table.tsx
│   └── lib/db.ts               # better-sqlite3 (read-only handle)
└── docs/superpowers/specs/
    └── 2026-04-28-m8550-monitor-design.md
```

## Data model

```sql
CREATE TABLE samples (
  ts          INTEGER PRIMARY KEY,    -- unix seconds
  rx_total    INTEGER,                -- cumulative bytes from router (NULL when offline)
  tx_total    INTEGER,
  rx_rate     INTEGER,                -- bytes/sec, derived in collector
  tx_rate     INTEGER,
  online      INTEGER NOT NULL        -- 0/1; 0 means router unreachable
);

CREATE TABLE clients (
  ts          INTEGER,
  mac         TEXT,
  name        TEXT,
  ip          TEXT,
  rx_rate     INTEGER,                -- bytes/sec at this tick
  tx_rate     INTEGER,
  PRIMARY KEY (ts, mac)
);
CREATE INDEX idx_clients_ts ON clients(ts);

PRAGMA journal_mode=WAL;
```

If recon shows the router only exposes per-client cumulative byte counters (not rates), the collector computes per-client rates the same way it does for totals before insert. Either way the schema stays the same — `rx_rate` / `tx_rate` are always derived, never raw.

Retention is unbounded for v1. Disk usage at 5s intervals: ~17.3k sample rows/day. Per-client rows depend on connected device count. Fine on any modern disk for at least a year. Pruning can be added later.

## Rate calculation

For totals, in the collector:

```
dt = ts[t] - ts[t-1]
rx_rate = (rx_total[t] - rx_total[t-1]) / dt
```

Edge cases:

- `rx_total[t] < rx_total[t-1]` (counter reset, e.g. router reboot) → store `rx_rate = NULL` for that tick. The chart breaks the line on NULLs.
- `dt > 2 * POLL_INTERVAL` (missed ticks while we were offline / paused) → don't compute a rate; store `online=0` rows for the gap so the chart line breaks.
- First tick after start → no previous sample, `rx_rate = NULL`.

Same logic applies to per-client rates if we have to derive them.

## HTTP API (Next.js)

| Method | Path | Returns |
|---|---|---|
| GET | `/api/current` | Latest `samples` row + latest `clients` rows for that ts. JSON. |
| GET | `/api/history?range=1h\|24h\|7d` | Time series of `(ts, rx_rate, tx_rate, online)`. Server downsamples to ~500 points to keep payload small. |

Both routes read `DB_PATH` from env, open SQLite read-only.

## UI

Single page at `/`:

- **Header strip** — big ↓ / ↑ rates (Mb/s, auto-scale to Kb/s for low rates), client count, online/offline pill.
- **Chart** — dual-line (rx, tx) with range selector buttons: 1h · 24h · 7d. Recharts. Y axis auto-scales.
- **Clients table** — `name · IP · MAC · ↓ · ↑`, sortable by any column. Shows current tick only (last `clients` rows).

Browser polls `/api/current` every 5s. Chart re-fetches `/api/history` only on range change.

No dark/light mode toggle in v1. Pick a sensible single theme.

## Error handling

| Failure | Collector behaviour | UI behaviour |
|---|---|---|
| Router unreachable (off-WiFi, asleep, container can't reach LAN) | Log; write `online=0` row; back off poll to 30s while down; resume 5s on success | "Router offline" pill; chart line breaks |
| Login expired / session 401 | Re-login transparently; if login itself fails, treat as unreachable | (none) |
| Counter reset | `rate = NULL` for the tick | Line break in chart |
| DB locked | Retry once after 100ms; otherwise log+drop tick | Last good sample shown |
| Collector down | (n/a — process is gone) | Header ages out: pill turns "stale" if newest sample > 30s old |

## Docker / Compose

`compose.yaml`:

```yaml
services:
  collector:
    build: ./collector
    volumes:
      - ./data:/data
    environment:
      - M8550_HOST=192.168.1.1
      - M8550_PASSWORD=${M8550_PASSWORD}
      - DB_PATH=/data/m8550.db
      - POLL_INTERVAL=5
    restart: unless-stopped

  web:
    build: ./web
    ports:
      - "3000:3000"
    volumes:
      - ./data:/data:ro
    environment:
      - DB_PATH=/data/m8550.db
    restart: unless-stopped
    depends_on:
      - collector
```

Secrets live in `.env` (gitignored). `.env.example` is committed.

### Networking caveat

The collector container has to reach `192.168.1.1` on the host's LAN. From Docker Desktop on macOS this normally works via the bridge → host NAT path, but is not guaranteed on every config. **Verified during recon** by running `docker run --rm alpine ping -c 1 192.168.1.1` before any collector code is written. If that fails, fall back to one of:

- Run collector natively with `uv run`, keep `web` containerised.
- Enable Docker Desktop's host networking (4.34+) for the collector service.

This decision is made during the recon phase, not pre-emptively.

## Implementation phases

1. **Recon** — capture browser → `192.168.1.1` traffic, document login flow and the endpoint(s) for traffic totals + connected clients. Verify Docker container can reach `192.168.1.1`. Throwaway artefact: a recon notes file in `docs/`.
2. **Router client** — try `tplinkrouterc6u` against the M8550. If it works, use it as a dependency. If not, hand-roll the auth + fetch in `router.py` from the recon notes.
3. **Collector + SQLite** — `poller.py`, `store.py`, `__main__.py`. Schema migration on startup. Native run first, Dockerfile right after.
4. **Next.js scaffold + API routes** — bootstrap with `pnpm create next-app`, add `better-sqlite3`, write `current` and `history` routes. Verify against a populated DB.
5. **Dashboard UI** — `rate-card`, `traffic-chart`, `clients-table`. Wire polling. Range selector.
6. **Compose + .env + README** — finalise `compose.yaml`, write `.env.example`, write the README run instructions.
7. **Polish** — error states (offline pill, stale pill), tighten UI spacing, handle empty-DB / first-run case gracefully.

Each phase ends in a working state. No phase depends on later-phase code.

## Testing

- **Unit (Python)** — `poller` rate calc: deltas, counter resets, gaps, first tick. Pure functions, no I/O.
- **Unit (Python)** — `store` against in-memory SQLite (`:memory:`).
- **Recorded fixtures (Python)** — captured HTTP responses from recon, replayed against `router.py` so CI doesn't need a live router.
- **Manual smoke (UI)** — populate `data/m8550.db` with synthetic samples, verify dashboard renders correctly with full / partial / empty data.

No e2e or browser tests in v1. The UI is small enough that manual verification is faster than maintaining Playwright.

## Out of scope (v1)

- Authentication on the dashboard.
- Multi-device / multi-router support.
- Historical retention / pruning policy.
- Alerts (e.g. "rate > X for Y seconds").
- Mobile-specific layouts (responsive enough to be readable on a phone, but not optimised).
- Anything that requires the M8550 cloud API.
- Home Assistant integration.

## Open questions, deferred

- Exact endpoint paths and auth flow on the M8550 — answered in phase 1 (recon), not now.
- Whether `tplinkrouterc6u` works for this specific model — answered in phase 2.
- Per-client byte data shape — answered in phase 1.
