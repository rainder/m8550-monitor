import sqlite3
from contextlib import contextmanager
from pathlib import Path


SCHEMA = """
CREATE TABLE IF NOT EXISTS samples (
    ts            INTEGER PRIMARY KEY,
    total_bytes   INTEGER,
    rx_rate       INTEGER,
    tx_rate       INTEGER,
    online        INTEGER NOT NULL
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
    ) -> None:
        with self._connect() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO samples "
                "(ts, total_bytes, rx_rate, tx_rate, online) "
                "VALUES (?, ?, ?, ?, ?)",
                (ts, total_bytes, rx_rate, tx_rate, int(online)),
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
