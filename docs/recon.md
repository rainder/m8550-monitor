# M8550 Recon Notes

## Decisions summary

| Question | Answer |
|---|---|
| Container reaches 192.168.1.1? | **yes** (0% packet loss) |
| Use `tplinkrouterc6u`? | **yes**, picked client = `TPLinkEXClient`, `username="user"` |
| Source for current ↓ / ↑ rates (WAN total) | `client.get_lte_status()` → `cur_rx_speed` / `cur_tx_speed` (bytes/sec) |
| Source for cumulative bytes (WAN) | `client.get_lte_status()` → `total_statistics` (single combined counter) |
| Source for connected-clients list | `client.get_status()` → `status.devices` (mac, ip, hostname, conn type, active) |
| Source for **per-client** traffic | `client.req_act([ActItem(GL, "DEV2_STAT_ENTRY")])` → `totalBytes` (combined cumulative) per MAC. Compute delta to get rate. |
| **Per-client RX/TX split available?** | **NO** — only combined. Tried `STAT_ENTRY`, expanded `DEV2_STAT_ENTRY` attrs (`Rx`/`Tx` variants), and ~12 other candidate OIDs (`DEV2_HOST_TRAFFIC`, `DEV2_TRAFFIC_STATS`, `DEV2_RATE_ENTRY`, …) — all returned "not supported". |

## 1. Docker reachability to 192.168.1.1

- Command: `docker run --rm alpine ping -c 3 192.168.1.1`
- Outcome: 3 packets transmitted, 3 received, 0% packet loss (RTT 9.7/52.9/112.7 ms avg/min/max).
- **Decision:** collector runs in container.

## 2. tplinkrouterc6u compatibility

- Library version: 5.18.1
- Provider auto-pick: **`TPLinkEXClient`**.
- Default `username="admin"` fails (`"Login failed, wrong user or password. Try to pass user instead of admin in username"`). `username="user"` succeeds.

## 3. WAN totals — `get_lte_status()`

```
total_statistics: 613212528172   # combined cumulative bytes (RX+TX)
cur_rx_speed:    2256407         # bytes/sec, current download
cur_tx_speed:    85807           # bytes/sec, current upload
```

`cur_rx_speed` / `cur_tx_speed` are the WAN download / upload rates as the router reports them. **No delta math needed** for WAN totals — the router gives the rates directly.

## 4. Client list — `get_status()`

```
Device(
  type=Connection.HOST_2G | HOST_5G | WIRED,
  _macaddr,
  _ipaddr,
  hostname,
  active,
  # all of these are NULL on the M8550:
  packets_sent, packets_received,
  down_speed, up_speed, tx_rate, rx_rate,
  online_time, traffic_usage, signal,
)
```

Use this for the basic client list. Per-host traffic comes from the next endpoint.

## 5. Per-client traffic — `DEV2_STAT_ENTRY`

Reached via the library's low-level `req_act` API:

```python
acts = [router.ActItem(router.ActItem.GL, "DEV2_STAT_ENTRY")]
_, values = router.req_act(acts)
# values[0] is a list of dicts, one per active host:
# {
#   "ipAddress":  "3232235782",     # int-encoded IPv4 (big-endian; 3232235782 = 192.168.1.11)
#   "macAddress": "AA:BB:CC:DD:EE:02",
#   "totalPkts":  "1193751",
#   "totalBytes": "651392471",      # cumulative since router boot, COMBINED RX+TX
#   "currPkts":   "116",
#   "currBytes":  "15057",          # bytes in current sampling window (NOT bytes/sec exactly)
#   "currIcmp", "currUdp", "currSyn", ...   # connection-state diagnostics
#   "stack":      "1,0,0,0,0,0",
# }
```

### Verified by sampling twice 5 s apart

```
sample 1: Laptop (AA:BB:CC:DD:EE:02) totalBytes=651477826 currBytes=17230
sample 2: Laptop (AA:BB:CC:DD:EE:02) totalBytes=651478588 currBytes=22070
delta: 762 bytes over 5 s → 152 B/s combined
```

`totalBytes` is a true monotonic counter — use **delta of `totalBytes`** to compute per-client current bandwidth (combined RX+TX).

`currBytes` looks like an internal sampling-window value, not stable bytes/sec; don't use it for charts.

## 6. Implications for spec / plan

| Spec assumption | Reality |
|---|---|
| Cumulative `rx_total` + `tx_total` per WAN | One combined `total_bytes` (`total_statistics`) instead. Drop separate columns. |
| Compute WAN rates by delta | Not needed — router gives `cur_rx_speed` / `cur_tx_speed` directly. The `rate.py` module is unnecessary for WAN. |
| Per-client `rx_rate` + `tx_rate` | Not available. Only combined. Compute as delta of per-client `totalBytes`. |
| Clients table columns: `name · IP · MAC · ↓ · ↑` | Becomes `name · IP · MAC · conn (2.4G/5G) · ↕ combined`. |

### Decision summary

The spec needs the following adjustments before Phase 1 starts:

- **Schema:** drop `samples.rx_total` / `samples.tx_total`. Add `samples.total_bytes` (combined cumulative). Keep `samples.rx_rate` / `tx_rate` (now stored as-is from router, not derived). Drop `clients.rx_rate` / `clients.tx_rate`. Add `clients.bandwidth` (B/s combined, derived from `totalBytes` delta) and `clients.total_bytes` (cumulative).
- **`rate.py`:** still needed — for per-client `bandwidth` from `totalBytes` deltas. Keep but applied per client only.
- **UI:** clients table loses ↓/↑ columns, gains a single ↕ combined column and a connection-type indicator (2.4G / 5G / wired).
