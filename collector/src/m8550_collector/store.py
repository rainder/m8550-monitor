import sqlite3
from contextlib import contextmanager
from pathlib import Path


SCHEMA = """
CREATE TABLE IF NOT EXISTS samples (
    ts              INTEGER PRIMARY KEY,
    total_bytes     INTEGER,
    rx_rate         INTEGER,
    tx_rate         INTEGER,
    online          INTEGER NOT NULL,
    sig_level       INTEGER,
    rsrp            INTEGER,
    rsrq            INTEGER,
    snr             INTEGER,
    isp_name        TEXT,
    cpu_pct         REAL,
    mem_pct         REAL,
    connected_band  TEXT,
    endc_status     INTEGER,
    network_type    INTEGER,
    wan_ipv4        TEXT,
    wan_ipv6        TEXT,
    ss_rsrp              INTEGER,
    ss_rsrq              INTEGER,
    ss_sinr              INTEGER,
    nr_signal_strength   INTEGER,
    nr_band              TEXT,
    lte_signal_strength  INTEGER,
    lte_band             TEXT
);

CREATE TABLE IF NOT EXISTS clients (
    ts            INTEGER,
    mac           TEXT,
    name          TEXT,
    ip            TEXT,
    conn_type     TEXT,
    total_bytes   INTEGER,
    bandwidth     INTEGER,
    PRIMARY KEY (ts, mac)
);

CREATE INDEX IF NOT EXISTS idx_clients_ts ON clients(ts);

CREATE TABLE IF NOT EXISTS sms_messages (
    id           INTEGER PRIMARY KEY,
    sender       TEXT NOT NULL,
    content      TEXT NOT NULL,
    received_at  INTEGER NOT NULL,
    unread       INTEGER NOT NULL,
    synced_at    INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS push_subscriptions (
    endpoint     TEXT PRIMARY KEY,
    p256dh       TEXT NOT NULL,
    auth         TEXT NOT NULL,
    created_at   INTEGER NOT NULL
);
"""


class Store:
    def __init__(self, path: str):
        self.path = path

    @contextmanager
    def _connect(self):
        Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(self.path)
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def init_schema(self) -> None:
        with self._connect() as conn:
            conn.execute("PRAGMA journal_mode=WAL")
            conn.executescript(SCHEMA)

    def append_sample(
        self,
        ts: int,
        total_bytes: int | None,
        rx_rate: int | None,
        tx_rate: int | None,
        online: bool,
        wan_status=None,   # WanStatus | None — typed loosely to avoid circular imports
    ) -> None:
        w = wan_status
        with self._connect() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO samples ("
                "ts, total_bytes, rx_rate, tx_rate, online, "
                "sig_level, rsrp, rsrq, snr, isp_name, cpu_pct, mem_pct, "
                "connected_band, endc_status, network_type, wan_ipv4, wan_ipv6, "
                "ss_rsrp, ss_rsrq, ss_sinr, nr_signal_strength, nr_band, "
                "lte_signal_strength, lte_band"
                ") VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    ts, total_bytes, rx_rate, tx_rate, int(online),
                    w.sig_level if w else None,
                    w.rsrp      if w else None,
                    w.rsrq      if w else None,
                    w.snr       if w else None,
                    w.isp_name  if w else None,
                    w.cpu_pct   if w else None,
                    w.mem_pct   if w else None,
                    w.connected_band if w else None,
                    w.endc_status    if w else None,
                    w.network_type   if w else None,
                    w.wan_ipv4       if w else None,
                    w.wan_ipv6       if w else None,
                    w.ss_rsrp              if w else None,
                    w.ss_rsrq              if w else None,
                    w.ss_sinr              if w else None,
                    w.nr_signal_strength   if w else None,
                    w.nr_band              if w else None,
                    w.lte_signal_strength  if w else None,
                    w.lte_band             if w else None,
                ),
            )

    def append_clients(self, ts: int, clients: list[dict]) -> None:
        if not clients:
            return
        with self._connect() as conn:
            conn.executemany(
                "INSERT OR REPLACE INTO clients "
                "(ts, mac, name, ip, conn_type, total_bytes, bandwidth) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                [
                    (
                        ts,
                        c["mac"],
                        c.get("name"),
                        c.get("ip"),
                        c.get("conn_type"),
                        c.get("total_bytes"),
                        c.get("bandwidth"),
                    )
                    for c in clients
                ],
            )

    def last_client_totals(self) -> dict[str, tuple[int, int]]:
        """Latest (ts, total_bytes) per MAC. Used by the poller for delta calc."""
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT mac, ts, total_bytes FROM clients "
                "WHERE (mac, ts) IN ("
                "   SELECT mac, MAX(ts) FROM clients GROUP BY mac"
                ")"
            ).fetchall()
            return {mac: (ts, total) for mac, ts, total in rows}

    def replace_sms(self, ts: int, messages) -> list:
        """Full-mirror the router's inbox: replace our cached rows so deleted
        messages disappear and unread/content edits apply. Returns the
        subset of ``messages`` whose ids were not in our cache before this
        call — these are the freshly-arrived ones the caller may want to
        push-notify on. Treats the first-ever sync (cache empty) as having
        no new messages so that adding the feature doesn't notify on the
        existing inbox backlog."""
        with self._connect() as conn:
            prev_ids: set[int] = {
                row[0] for row in conn.execute("SELECT id FROM sms_messages")
            }
            had_cache_before = bool(prev_ids)
            conn.execute("DELETE FROM sms_messages")
            conn.executemany(
                "INSERT INTO sms_messages "
                "(id, sender, content, received_at, unread, synced_at) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                [
                    (m.id, m.sender, m.content, m.received_at, int(m.unread), ts)
                    for m in messages
                ],
            )
        if not had_cache_before:
            return []
        return [m for m in messages if m.id not in prev_ids]

    def list_push_subscriptions(self) -> list[dict]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT endpoint, p256dh, auth FROM push_subscriptions"
            ).fetchall()
        return [
            {"endpoint": r[0], "p256dh": r[1], "auth": r[2]} for r in rows
        ]

    def add_push_subscription(
        self, endpoint: str, p256dh: str, auth: str, created_at: int,
    ) -> None:
        with self._connect() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO push_subscriptions "
                "(endpoint, p256dh, auth, created_at) VALUES (?, ?, ?, ?)",
                (endpoint, p256dh, auth, created_at),
            )

    def delete_push_subscriptions(self, endpoints) -> None:
        endpoints = list(endpoints)
        if not endpoints:
            return
        with self._connect() as conn:
            conn.executemany(
                "DELETE FROM push_subscriptions WHERE endpoint = ?",
                [(e,) for e in endpoints],
            )

    def list_sms(self) -> list[dict]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT id, sender, content, received_at, unread, synced_at "
                "FROM sms_messages ORDER BY received_at DESC, id DESC"
            ).fetchall()
        return [
            {
                "id": r[0],
                "sender": r[1],
                "content": r[2],
                "received_at": r[3],
                "unread": bool(r[4]),
                "synced_at": r[5],
            }
            for r in rows
        ]

    def latest_sample(self) -> dict | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT ts, total_bytes, rx_rate, tx_rate, online "
                "FROM samples ORDER BY ts DESC LIMIT 1"
            ).fetchone()
            if row is None:
                return None
            return {
                "ts": row[0],
                "total_bytes": row[1],
                "rx_rate": row[2],
                "tx_rate": row[3],
                "online": bool(row[4]),
            }
