from unittest.mock import MagicMock

import pytest

from m8550_collector.router import (
    AuthError,
    LibRouterClient,
    RouterClientSnapshot,
    RouterSnapshot,
)


def _device(mac, name, ip, conn_value):
    """Mimic the library's Device dataclass enough for our adapter."""
    d = MagicMock()
    d._macaddr = MagicMock()
    d._macaddr.__str__ = lambda self=d: mac  # whatever the library would render
    d._ipaddr = MagicMock()
    d._ipaddr.__str__ = lambda self=d: ip
    d.hostname = name
    d.active = True
    conn = MagicMock()
    conn.value = conn_value
    d.type = conn
    return d


def test_snapshot_combines_lte_status_status_and_dev2_stat(monkeypatch):
    fake_lib = MagicMock()

    lte = MagicMock()
    lte.total_statistics = 613_000_000_000
    lte.cur_rx_speed = 2_000_000
    lte.cur_tx_speed = 80_000
    fake_lib.get_lte_status.return_value = lte

    status = MagicMock()
    status.devices = [
        _device("AA-BB-CC-DD-EE-01", "Phone", "192.168.1.10", "host_5g"),
        _device("AA-BB-CC-DD-EE-02", "Laptop",  "192.168.1.11", "host_5g"),
    ]
    fake_lib.get_status.return_value = status

    fake_lib.ActItem = MagicMock()
    fake_lib.ActItem.GL = "gl"
    fake_lib.req_act.return_value = (
        "raw",
        [[
            {"macAddress": "AA:BB:CC:DD:EE:01", "totalBytes": "184498626"},
            {"macAddress": "AA:BB:CC:DD:EE:02", "totalBytes": "651477826"},
        ]],
    )

    client = LibRouterClient(_lib=fake_lib)
    snap = client.snapshot()

    assert snap.total_bytes == 613_000_000_000
    assert snap.rx_rate == 2_000_000
    assert snap.tx_rate == 80_000
    assert sorted(snap.clients, key=lambda c: c.mac) == sorted([
        RouterClientSnapshot(mac="AA:BB:CC:DD:EE:01", name="Phone",
                              ip="192.168.1.10", conn_type="host_5g",
                              total_bytes=184_498_626),
        RouterClientSnapshot(mac="AA:BB:CC:DD:EE:02", name="Laptop",
                              ip="192.168.1.11", conn_type="host_5g",
                              total_bytes=651_477_826),
    ], key=lambda c: c.mac)


def test_snapshot_handles_missing_stat_entry_for_known_device():
    """A device exists in get_status() but has no DEV2_STAT_ENTRY row → total_bytes=None."""
    fake_lib = MagicMock()

    lte = MagicMock()
    lte.total_statistics = 1
    lte.cur_rx_speed = 0
    lte.cur_tx_speed = 0
    fake_lib.get_lte_status.return_value = lte

    status = MagicMock()
    status.devices = [_device("AA-BB-CC-DD-EE-FF", "ghost", "1.2.3.4", "host_2g")]
    fake_lib.get_status.return_value = status

    fake_lib.ActItem = MagicMock()
    fake_lib.ActItem.GL = "gl"
    fake_lib.req_act.return_value = ("raw", [[]])  # empty list of stats

    client = LibRouterClient(_lib=fake_lib)
    snap = client.snapshot()

    assert len(snap.clients) == 1
    assert snap.clients[0].mac == "AA:BB:CC:DD:EE:FF"
    assert snap.clients[0].total_bytes is None


def test_snapshot_drops_inactive_devices():
    fake_lib = MagicMock()

    lte = MagicMock()
    lte.total_statistics = 1
    lte.cur_rx_speed = 0
    lte.cur_tx_speed = 0
    fake_lib.get_lte_status.return_value = lte

    active = _device("AA-BB-CC-DD-EE-01", "live", "1.1.1.1", "host_5g")
    inactive = _device("AA-BB-CC-DD-EE-02", "ghost", "1.1.1.2", "host_5g")
    inactive.active = False
    status = MagicMock()
    status.devices = [active, inactive]
    fake_lib.get_status.return_value = status

    fake_lib.ActItem = MagicMock()
    fake_lib.ActItem.GL = "gl"
    fake_lib.req_act.return_value = ("raw", [[]])

    client = LibRouterClient(_lib=fake_lib)
    snap = client.snapshot()

    assert {c.mac for c in snap.clients} == {"AA:BB:CC:DD:EE:01"}


def test_snapshot_unreachable_raises_connection_error():
    """Library exceptions during data fetch surface as ConnectionError."""
    from tplinkrouterc6u.common.exception import ClientException

    fake_lib = MagicMock()
    fake_lib.get_lte_status.side_effect = ClientException("boom")

    client = LibRouterClient(_lib=fake_lib)
    with pytest.raises(ConnectionError):
        client.snapshot()


def test_snapshot_oserror_also_raises_connection_error():
    fake_lib = MagicMock()
    fake_lib.get_lte_status.side_effect = OSError("connection refused")

    client = LibRouterClient(_lib=fake_lib)
    with pytest.raises(ConnectionError):
        client.snapshot()
