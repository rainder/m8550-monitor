# M8550 Recon Notes

## Decisions summary

| Question | Answer |
|---|---|
| Container reaches 192.168.1.1? | **yes** (0% packet loss) |
| Use `tplinkrouterc6u`? | **yes**, picked client = `TPLinkEXClient`, `username="user"` |
| Source for current ↓ / ↑ rates | `client.get_lte_status()` → `cur_rx_speed` / `cur_tx_speed` (bytes/sec, already a rate) |
| Source for cumulative bytes | `client.get_lte_status()` → `total_statistics` (single counter, combined RX+TX) |
| Source for connected-clients list | `client.get_status()` → `status.devices` (mac, ip, hostname, connection type, active) |
| **Per-client bandwidth available?** | **NO** — all device traffic fields (`down_speed`, `up_speed`, `rx_rate`, `tx_rate`, `traffic_usage`) come back as `null`. The M8550 web UI itself doesn't appear to expose per-device traffic via this path. |

## 1. Docker reachability to 192.168.1.1

- Command: `docker run --rm alpine ping -c 3 192.168.1.1`
- Outcome: 3 packets transmitted, 3 received, 0% packet loss (RTT min/avg/max = 9.7/52.9/112.7 ms)
- **Decision:** collector runs in container.

## 2. tplinkrouterc6u compatibility

- Library version: 5.18.1
- Provider auto-pick: **`TPLinkEXClient`** (matched via `supports()` on M8550's web UI signature).
- Default `username="admin"` fails with `"Login failed, wrong user or password. Try to pass user instead of admin in username"`.
- `username="user"` succeeds.

### Status from `get_status()`

```
_lan_macaddr: AA-BB-CC-DD-EE-01
_wan_ipv4_addr: 100.64.1.1 (MBB / mobile broadband)
_lan_ipv4_addr: 192.168.1.1
wifi_clients_total: 4
clients_total: 4
mem_usage: 0.52
cpu_usage: 0.59
wifi_2g_enable: true
wifi_5g_enable: true
devices: [...]            # see below
```

### Devices from `get_status()`

Each `Device`:
- `_macaddr` (EUI48), `_ipaddr` (IPv4Address), `hostname` (str), `active` (bool), `type` (Connection enum: HOST_2G / HOST_5G / WIRED).
- `packets_sent`, `packets_received`, `down_speed`, `up_speed`, `tx_rate`, `rx_rate`, `online_time`, `traffic_usage`, `signal` — **all None on the M8550.**

### LTE status from `get_lte_status()`

```
enable: 1
connect_status: 4
network_type: 8
sim_status: 3
total_statistics: 613212528172    # cumulative bytes (single combined counter)
cur_rx_speed: 2256407             # bytes/sec current
cur_tx_speed: 85807               # bytes/sec current
sms_unread_count: 3
sig_level / rsrp / rsrq / snr: 0  # signal not populated in this state
isp_name: Bite
```

### IPv4 status from `get_ipv4_status()`

```
_wan_macaddr: 00-00-00-00-00-00
_wan_ipv4_ipaddr: 100.64.1.1
_wan_ipv4_gateway: 100.64.1.254
_wan_ipv4_conntype: MBB
```

## 3. Implications for the design

The spec assumed cumulative RX/TX byte counters per WAN, plus per-client bandwidth. The M8550 actually exposes:

- **Current rates directly** (`cur_rx_speed`, `cur_tx_speed`) — better than computing from deltas; collector skips the rate-computation logic for totals.
- **Combined cumulative counter only** (`total_statistics`) — fine for tracking total data usage, but cannot recover separate RX/TX cumulatives from it.
- **Per-device traffic: not available.** Names / IPs / MACs / 2G-or-5G yes; bandwidth no.

### Spec deltas requiring user decision

1. **Schema:** `samples.rx_total` / `tx_total` not populated by router. Either drop them or repurpose as `total_bytes` (single combined). `rx_rate` / `tx_rate` come straight from router (no delta math).
2. **Per-client bandwidth in the dashboard:** spec calls for it; router can't supply it. Fallback: clients table shows name / IP / MAC / connection (2.4G/5G/wired) / active — no rate columns.
3. **Rate-calculation edge cases** (counter wrap, missing prev sample) become moot for totals since the router gives rates directly. The `online=0` gap-handling logic still applies.
