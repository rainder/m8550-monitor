# Extra ops features — implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development.

**Goal:** Surface three additional pieces of data the M8550 already exposes via `tplinkrouterc6u`:

1. **Signal panel** — RSRP / RSRQ / SNR + a 0-5 bar level. Defining widget for a 5G mobile router.
2. **CPU + memory gauges** — thin inline indicators in the header strip. Operational hygiene.
3. **Total data used** — combined cumulative WAN bytes. Useful when the SIM has a data cap.

All three values come from one extra read of `client.get_lte_status()` (signal) and `client.get_status()` (cpu/mem). We already call both — we're just throwing data away. So the cost is plumbing, not new I/O.

**Architecture stays the same:** collector writes new columns into the existing `samples` table; web reads them through `/api/current`; new presentational components render them. No new API endpoints, no new tables.

---

## Schema delta

`samples` gains seven nullable columns:

```sql
ALTER TABLE samples ADD COLUMN sig_level     INTEGER;   -- 0..5 bars
ALTER TABLE samples ADD COLUMN rsrp          INTEGER;   -- dBm (typically -40..-140)
ALTER TABLE samples ADD COLUMN rsrq          INTEGER;   -- dB  (typically -3..-20)
ALTER TABLE samples ADD COLUMN snr           INTEGER;   -- dB
ALTER TABLE samples ADD COLUMN isp_name      TEXT;      -- e.g. "Bite"
ALTER TABLE samples ADD COLUMN cpu_pct       REAL;      -- 0..1
ALTER TABLE samples ADD COLUMN mem_pct       REAL;      -- 0..1
```

`network_type` (`int` per recon) we'll skip for v1 — its decoding is firmware-specific and the carrier name + signal already tell the user enough.

The schema is created with `CREATE TABLE IF NOT EXISTS` from scratch; for existing DBs the implementer must use `ALTER TABLE` migrations or the simpler "wipe `data/m8550.db` and let it recreate" approach. We choose the latter: this is a single-user local app, the DB is regenerable, and the plan instructs the implementer to delete it.

`RouterSnapshot` gains a nested `wan_status` block to keep the per-tick metadata grouped:

```python
@dataclass(frozen=True)
class WanStatus:
    sig_level: int | None    # 0..5
    rsrp: int | None
    rsrq: int | None
    snr: int | None
    isp_name: str | None
    cpu_pct: float | None
    mem_pct: float | None

@dataclass(frozen=True)
class RouterSnapshot:
    total_bytes: int | None
    rx_rate: int | None
    tx_rate: int | None
    wan_status: WanStatus              # NEW
    clients: list[RouterClientSnapshot]
```

`Store.append_sample` widens to accept the new fields.

---

## Web type delta

```typescript
export interface Sample {
  ts: number
  rxRate: number | null
  txRate: number | null
  online: boolean
  totalBytes: number | null    // NEW — already in DB; just expose
  sigLevel: number | null      // NEW
  rsrp: number | null          // NEW
  rsrq: number | null          // NEW
  snr: number | null           // NEW
  ispName: string | null       // NEW
  cpuPct: number | null        // NEW
  memPct: number | null        // NEW
}
```

`db.ts.latestSample()` selects the new columns; `/api/current` returns them automatically (response is `{ sample, clients, ageSeconds }` and `Sample` is the value type).

---

## UI components

### `components/signal-panel.tsx` (new)

A single panel beside (or below) the rate cards:

```
┌────────────────────────────────────────────────┐
│ SIGNAL · BITE 5G                          ▮▮▮▯▯ │
│                                                │
│ RSRP    -82 dBm     RSRQ    -10 dB             │
│ SNR      14 dB                                 │
└────────────────────────────────────────────────┘
```

- Title: `SIGNAL` (uppercase mono), then `· {ispName}` after it. Bars (5 cells) on the right; filled count comes from `sigLevel`. Colour the filled cells by quality: green if level ≥ 4, amber if 2–3, red if ≤ 1.
- Body: three two-column rows showing RSRP / RSRQ / SNR. Numbers are `tabular-nums font-mono`, units (`dBm`, `dB`) in `text-zinc-500`.
- All-NULL values render as `—`.

Place this in the same row as the stat cards (3-column grid on desktop, stacked on mobile).

### `components/system-gauges.tsx` (new)

Inline gauge pair in the page header:

```
CPU  ▰▰▰▰▱▱  59 %       MEM  ▰▰▰▰▰▱  52 %
```

- Each gauge: 6 unicode block cells; filled count = `round(pct * 6)`. After the bar, show `XX %` in mono.
- Empty cells are `text-zinc-700`; filled cells are `text-zinc-300` (or amber/red at higher utilisation: ≥ 0.8 amber, ≥ 0.95 red).
- The header already has the `Clients · Updated · Status` block — these gauges sit to the LEFT of that block, separated by the existing `border-l` divider style.

### Total-data-used pill (small)

Not a new component — extend `app/page.tsx`. Below the two stat cards, add a single line of mono text:

```
TOTAL · 613.21 GB used
```

Use `formatBytes(totalBytes)` from `lib/format.ts`. Right-align under the cards (use `text-right`) or render as a tiny chip in the rate-card area — choose whichever looks cleanest at desktop width. If unclear, prefer a single-line chip after both cards.

---

## Phases / subagent dispatches

The implementation is small; dispatch in three passes.

### Pass 1 — Collector backend (one dispatch, sonnet)

Touches:
- `collector/src/m8550_collector/router.py` — `WanStatus` dataclass; `RouterSnapshot.wan_status`; `LibRouterClient.snapshot()` extracts new fields from `lte` and `status`.
- `collector/src/m8550_collector/store.py` — schema columns; `append_sample` widens.
- `collector/src/m8550_collector/poller.py` — pass `snap.wan_status` fields into `append_sample`.
- `collector/tests/test_store.py` — schema test asserts new columns; new `append_sample` columns asserted.
- `collector/tests/test_poller.py` — fix existing `RouterSnapshot(...)` constructions to include `wan_status=...`.
- `collector/tests/test_router_lib.py` — assert new fields surface in `LibRouterClient.snapshot()`.

Smoke test: delete `data/m8550.db`, restart `docker compose`, verify `/api/current` returns the new fields populated (after the API plumbing in Pass 2).

### Pass 2 — Web API + types (one dispatch, haiku)

Touches:
- `web/lib/types.ts` — `Sample` widens.
- `web/lib/db.ts` — `latestSample()` select widens; mapping widens.

Manual smoke: `curl http://localhost:3000/api/current` should now show the new fields after collector has written at least one tick.

### Pass 3 — UI (one dispatch, sonnet)

Touches:
- `web/components/signal-panel.tsx` — new.
- `web/components/system-gauges.tsx` — new.
- `web/components/stat-card.tsx` — keep as-is; only the layout container changes.
- `web/app/page.tsx` — replace the 2-column stat-card grid with a 3-column row (DOWNLOAD · UPLOAD · SIGNAL); add the total-used line below; add `<SystemGauges />` to the header before the metric/status block.
- `web/lib/format.ts` — already exposes `formatBytes`; reused.

Smoke test: page renders with all new bits live, no console errors, type-check passes, vitest passes.

---

## Constraints

- Each pass commits at least once; sequence Writes before any commit.
- Do not change the existing `clients` table schema or any per-client logic.
- Do not add new API endpoints. Everything rides on the existing `/api/current` shape.
- If a value is missing or N/A for a tick (e.g. router returned null for `mem_usage`), every consumer must accept null and show `—` — same convention as for `rxRate`/`txRate`.
- After Pass 1, if the live router is currently reporting `0` across all signal numbers (recon noted this happens when stationary), DO NOT treat 0 as "no data". Render the literal value. We'll see real numbers when there's actual signal variation.
