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
