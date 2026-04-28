import sqlite3
from m8550_collector.store import Store


def test_init_creates_schema(tmp_path):
    db = tmp_path / "test.db"
    Store(str(db)).init_schema()

    conn = sqlite3.connect(db)
    tables = {
        row[0]
        for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        )
    }
    assert {"samples", "clients"} <= tables

    sample_cols = {
        row[1] for row in conn.execute("PRAGMA table_info(samples)")
    }
    assert sample_cols == {"ts", "total_bytes", "rx_rate", "tx_rate", "online"}

    client_cols = {
        row[1] for row in conn.execute("PRAGMA table_info(clients)")
    }
    assert client_cols == {
        "ts", "mac", "name", "ip", "conn_type", "total_bytes", "bandwidth"
    }


def test_init_is_idempotent(tmp_path):
    db = tmp_path / "test.db"
    Store(str(db)).init_schema()
    Store(str(db)).init_schema()  # should not raise


def test_init_enables_wal(tmp_path):
    db = tmp_path / "test.db"
    Store(str(db)).init_schema()

    conn = sqlite3.connect(db)
    mode = conn.execute("PRAGMA journal_mode").fetchone()[0]
    assert mode == "wal"
