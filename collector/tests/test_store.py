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
    assert sample_cols == {
        "ts", "total_bytes", "rx_rate", "tx_rate", "online",
        "sig_level", "rsrp", "rsrq", "snr", "isp_name", "cpu_pct", "mem_pct",
        "connected_band", "endc_status", "network_type", "wan_ipv4", "wan_ipv6",
    }

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


def test_append_sample_writes_row(tmp_path):
    db = tmp_path / "t.db"
    s = Store(str(db))
    s.init_schema()

    s.append_sample(
        ts=1700000000,
        total_bytes=1500,
        rx_rate=10,
        tx_rate=5,
        online=True,
    )

    conn = sqlite3.connect(db)
    row = conn.execute(
        "SELECT ts, total_bytes, rx_rate, tx_rate, online FROM samples"
    ).fetchone()
    assert row == (1700000000, 1500, 10, 5, 1)


def test_append_sample_offline_allows_null_totals(tmp_path):
    db = tmp_path / "t.db"
    s = Store(str(db))
    s.init_schema()

    s.append_sample(
        ts=1700000000,
        total_bytes=None,
        rx_rate=None,
        tx_rate=None,
        online=False,
    )

    conn = sqlite3.connect(db)
    row = conn.execute(
        "SELECT ts, total_bytes, rx_rate, tx_rate, online FROM samples"
    ).fetchone()
    assert row == (1700000000, None, None, None, 0)


def test_append_clients_writes_rows(tmp_path):
    db = tmp_path / "t.db"
    s = Store(str(db))
    s.init_schema()

    s.append_clients(
        ts=1700000000,
        clients=[
            {"mac": "aa:bb", "name": "phone", "ip": "192.168.1.10",
             "conn_type": "host_2g", "total_bytes": 100000, "bandwidth": 100},
            {"mac": "cc:dd", "name": "laptop", "ip": "192.168.1.11",
             "conn_type": "host_5g", "total_bytes": 500000, "bandwidth": 200},
        ],
    )

    conn = sqlite3.connect(db)
    rows = conn.execute(
        "SELECT mac, name, conn_type, total_bytes, bandwidth FROM clients ORDER BY mac"
    ).fetchall()
    assert rows == [
        ("aa:bb", "phone", "host_2g", 100000, 100),
        ("cc:dd", "laptop", "host_5g", 500000, 200),
    ]


def test_append_clients_handles_empty_list(tmp_path):
    db = tmp_path / "t.db"
    s = Store(str(db))
    s.init_schema()

    s.append_clients(ts=1700000000, clients=[])

    conn = sqlite3.connect(db)
    count = conn.execute("SELECT COUNT(*) FROM clients").fetchone()[0]
    assert count == 0


def test_append_clients_allows_null_bandwidth(tmp_path):
    """First sample for a MAC has no prior total_bytes, so bandwidth is None."""
    db = tmp_path / "t.db"
    s = Store(str(db))
    s.init_schema()

    s.append_clients(
        ts=1700000000,
        clients=[{"mac": "aa", "name": "phone", "ip": "1.1.1.1",
                  "conn_type": "host_5g", "total_bytes": 1000, "bandwidth": None}],
    )

    conn = sqlite3.connect(db)
    row = conn.execute("SELECT bandwidth FROM clients").fetchone()
    assert row == (None,)


def test_latest_sample_returns_most_recent(tmp_path):
    db = tmp_path / "t.db"
    s = Store(str(db))
    s.init_schema()

    s.append_sample(1, total_bytes=100, rx_rate=None, tx_rate=None, online=True)
    s.append_sample(2, total_bytes=200, rx_rate=20, tx_rate=10, online=True)
    s.append_sample(3, total_bytes=300, rx_rate=20, tx_rate=10, online=True)

    latest = s.latest_sample()
    assert latest == {
        "ts": 3,
        "total_bytes": 300,
        "rx_rate": 20,
        "tx_rate": 10,
        "online": True,
    }


def test_latest_sample_none_when_empty(tmp_path):
    db = tmp_path / "t.db"
    s = Store(str(db))
    s.init_schema()
    assert s.latest_sample() is None


def test_latest_sample_marks_offline_correctly(tmp_path):
    db = tmp_path / "t.db"
    s = Store(str(db))
    s.init_schema()
    s.append_sample(1, total_bytes=None, rx_rate=None, tx_rate=None, online=False)
    latest = s.latest_sample()
    assert latest is not None and latest["online"] is False


def test_last_client_totals_returns_most_recent_per_mac(tmp_path):
    db = tmp_path / "t.db"
    s = Store(str(db))
    s.init_schema()

    s.append_clients(
        ts=10,
        clients=[
            {"mac": "aa", "name": "n", "ip": "i", "conn_type": "host_2g",
             "total_bytes": 100, "bandwidth": None},
            {"mac": "bb", "name": "n", "ip": "i", "conn_type": "host_5g",
             "total_bytes": 200, "bandwidth": None},
        ],
    )
    s.append_clients(
        ts=20,
        clients=[
            {"mac": "aa", "name": "n", "ip": "i", "conn_type": "host_2g",
             "total_bytes": 500, "bandwidth": 40},
        ],
    )

    assert s.last_client_totals() == {
        "aa": (20, 500),
        "bb": (10, 200),
    }


def test_last_client_totals_empty_when_no_clients(tmp_path):
    db = tmp_path / "t.db"
    s = Store(str(db))
    s.init_schema()
    assert s.last_client_totals() == {}


def test_append_sample_persists_wan_status(tmp_path):
    from m8550_collector.router import WanStatus
    db = tmp_path / "t.db"
    s = Store(str(db))
    s.init_schema()

    s.append_sample(
        ts=1,
        total_bytes=1000,
        rx_rate=10,
        tx_rate=5,
        online=True,
        wan_status=WanStatus(
            sig_level=4, rsrp=-82, rsrq=-10, snr=14,
            isp_name="Bite", cpu_pct=0.59, mem_pct=0.52,
            connected_band="B3;N40", endc_status=1, network_type=8,
            wan_ipv4="100.64.1.1", wan_ipv6="2001:db8::1",
        ),
    )

    conn = sqlite3.connect(db)
    row = conn.execute(
        "SELECT sig_level, rsrp, rsrq, snr, isp_name, cpu_pct, mem_pct, "
        "connected_band, endc_status, network_type, wan_ipv4, wan_ipv6 FROM samples"
    ).fetchone()
    assert row == (
        4, -82, -10, 14, "Bite", 0.59, 0.52,
        "B3;N40", 1, 8, "100.64.1.1", "2001:db8::1",
    )


def test_append_sample_offline_keeps_wan_status_null(tmp_path):
    db = tmp_path / "t.db"
    s = Store(str(db))
    s.init_schema()
    s.append_sample(ts=1, total_bytes=None, rx_rate=None,
                    tx_rate=None, online=False)
    conn = sqlite3.connect(db)
    row = conn.execute(
        "SELECT sig_level, rsrp, isp_name, cpu_pct, mem_pct FROM samples"
    ).fetchone()
    assert row == (None, None, None, None, None)
