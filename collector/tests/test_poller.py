import sqlite3

import pytest

from m8550_collector.poller import Poller
from m8550_collector.router import RouterSnapshot, RouterClientSnapshot, WanStatus
from m8550_collector.store import Store


def _wan_idle() -> WanStatus:
    """A WanStatus with all-None fields, for tests that don't care."""
    return WanStatus(sig_level=None, rsrp=None, rsrq=None, snr=None,
                     isp_name=None, cpu_pct=None, mem_pct=None,
                     connected_band=None, endc_status=None, network_type=None,
                     wan_ipv4=None, wan_ipv6=None)


class FakeRouter:
    def __init__(self, snapshots):
        self.snapshots = list(snapshots)

    def snapshot(self):
        if not self.snapshots:
            raise ConnectionError("no more snapshots")
        s = self.snapshots.pop(0)
        if isinstance(s, Exception):
            raise s
        return s


def _store(tmp_path):
    s = Store(str(tmp_path / "t.db"))
    s.init_schema()
    return s


def test_first_tick_writes_wan_rates_directly(tmp_path):
    store = _store(tmp_path)
    router = FakeRouter([
        RouterSnapshot(total_bytes=10_000, rx_rate=2_000_000, tx_rate=80_000,
                       wan_status=_wan_idle(), clients=[]),
    ])
    p = Poller(router, store, now=lambda: 100)

    p.tick()

    sample = store.latest_sample()
    assert sample == {
        "ts": 100, "total_bytes": 10_000,
        "rx_rate": 2_000_000, "tx_rate": 80_000,
        "online": True,
    }


def test_first_client_tick_has_null_bandwidth(tmp_path):
    store = _store(tmp_path)
    router = FakeRouter([
        RouterSnapshot(
            total_bytes=10_000, rx_rate=100, tx_rate=50,
            wan_status=_wan_idle(),
            clients=[
                RouterClientSnapshot(
                    mac="aa", name="phone", ip="1.1.1.1",
                    conn_type="host_5g", total_bytes=500_000,
                ),
            ],
        ),
    ])
    p = Poller(router, store, now=lambda: 100)

    p.tick()

    conn = sqlite3.connect(store.path)
    row = conn.execute(
        "SELECT mac, conn_type, total_bytes, bandwidth FROM clients"
    ).fetchone()
    assert row == ("aa", "host_5g", 500_000, None)


def test_second_tick_computes_per_client_bandwidth(tmp_path):
    store = _store(tmp_path)
    router = FakeRouter([
        RouterSnapshot(
            total_bytes=10_000, rx_rate=100, tx_rate=50,
            wan_status=_wan_idle(),
            clients=[
                RouterClientSnapshot(
                    mac="aa", name="phone", ip="1.1.1.1",
                    conn_type="host_5g", total_bytes=500_000,
                ),
            ],
        ),
        RouterSnapshot(
            total_bytes=11_000, rx_rate=200, tx_rate=80,
            wan_status=_wan_idle(),
            clients=[
                RouterClientSnapshot(
                    mac="aa", name="phone", ip="1.1.1.1",
                    conn_type="host_5g", total_bytes=505_000,
                ),
            ],
        ),
    ])
    clock = iter([100, 105])
    p = Poller(router, store, now=lambda: next(clock))

    p.tick()
    p.tick()

    conn = sqlite3.connect(store.path)
    row = conn.execute(
        "SELECT bandwidth FROM clients WHERE ts = 105"
    ).fetchone()
    assert row == (1000,)  # (505_000 - 500_000) / 5

    sample = store.latest_sample()
    assert sample["rx_rate"] == 200  # taken straight from router, no delta math
    assert sample["tx_rate"] == 80


def test_per_client_counter_reset_yields_null_bandwidth(tmp_path):
    store = _store(tmp_path)
    router = FakeRouter([
        RouterSnapshot(
            total_bytes=10, rx_rate=0, tx_rate=0,
            wan_status=_wan_idle(),
            clients=[RouterClientSnapshot(mac="aa", name=None, ip=None,
                                          conn_type="wired", total_bytes=500)],
        ),
        RouterSnapshot(
            total_bytes=20, rx_rate=0, tx_rate=0,
            wan_status=_wan_idle(),
            clients=[RouterClientSnapshot(mac="aa", name=None, ip=None,
                                          conn_type="wired", total_bytes=10)],
        ),
    ])
    clock = iter([100, 105])
    p = Poller(router, store, now=lambda: next(clock))

    p.tick()
    p.tick()

    conn = sqlite3.connect(store.path)
    row = conn.execute("SELECT bandwidth FROM clients WHERE ts = 105").fetchone()
    assert row == (None,)


def test_per_client_total_bytes_disappears_yields_null_bandwidth(tmp_path):
    """Tick 1: client has total_bytes=500_000. Tick 2: same MAC, total_bytes=None.
    Must NOT crash; bandwidth at tick 2 should be None."""
    store = _store(tmp_path)
    router = FakeRouter([
        RouterSnapshot(
            total_bytes=10, rx_rate=0, tx_rate=0,
            wan_status=_wan_idle(),
            clients=[RouterClientSnapshot(
                mac="aa", name=None, ip=None,
                conn_type="host_5g", total_bytes=500_000,
            )],
        ),
        RouterSnapshot(
            total_bytes=20, rx_rate=0, tx_rate=0,
            wan_status=_wan_idle(),
            clients=[RouterClientSnapshot(
                mac="aa", name=None, ip=None,
                conn_type="host_5g", total_bytes=None,
            )],
        ),
    ])
    clock = iter([100, 105])
    p = Poller(router, store, now=lambda: next(clock))

    p.tick()
    p.tick()  # must not raise

    import sqlite3
    conn = sqlite3.connect(store.path)
    row = conn.execute("SELECT bandwidth FROM clients WHERE ts = 105").fetchone()
    assert row == (None,)


def test_connection_error_writes_offline_row(tmp_path):
    store = _store(tmp_path)
    router = FakeRouter([ConnectionError("unreachable")])
    p = Poller(router, store, now=lambda: 100)

    p.tick()

    sample = store.latest_sample()
    assert sample == {
        "ts": 100, "total_bytes": None,
        "rx_rate": None, "tx_rate": None,
        "online": False,
    }
    conn = sqlite3.connect(store.path)
    count = conn.execute("SELECT COUNT(*) FROM clients").fetchone()[0]
    assert count == 0  # no clients written when router unreachable


def test_poller_persists_wan_status(tmp_path):
    store = _store(tmp_path)
    router = FakeRouter([
        RouterSnapshot(
            total_bytes=10_000, rx_rate=100, tx_rate=50,
            wan_status=WanStatus(sig_level=4, rsrp=-82, rsrq=-10, snr=14,
                                  isp_name="Bite", cpu_pct=0.59, mem_pct=0.52,
                                  connected_band="B3;N40", endc_status=1,
                                  network_type=8, wan_ipv4="10.0.0.1",
                                  wan_ipv6=None),
            clients=[],
        ),
    ])
    p = Poller(router, store, now=lambda: 100)
    p.tick()

    conn = sqlite3.connect(store.path)
    row = conn.execute(
        "SELECT sig_level, rsrp, isp_name, cpu_pct FROM samples"
    ).fetchone()
    assert row == (4, -82, "Bite", 0.59)
