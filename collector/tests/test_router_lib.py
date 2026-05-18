from unittest.mock import MagicMock

import pytest

from m8550_collector.router import (
    AuthError,
    LibRouterClient,
    RouterClientSnapshot,
    RouterSnapshot,
    WanStatus,
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
    lte.sig_level = 4
    lte.rsrp = -82
    lte.rsrq = -10
    lte.snr = 14
    lte.isp_name = "Bite"
    fake_lib.get_lte_status.return_value = lte

    status = MagicMock()
    status.devices = [
        _device("AA-BB-CC-DD-EE-01", "Phone", "192.168.1.10", "host_5g"),
        _device("AA-BB-CC-DD-EE-02", "Laptop",  "192.168.1.11", "host_5g"),
    ]
    status.cpu_usage = 0.59
    status.mem_usage = 0.52
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
    lte.sig_level = 4
    lte.rsrp = -82
    lte.rsrq = -10
    lte.snr = 14
    lte.isp_name = "Bite"
    fake_lib.get_lte_status.return_value = lte

    status = MagicMock()
    status.devices = [_device("AA-BB-CC-DD-EE-FF", "ghost", "1.2.3.4", "host_2g")]
    status.cpu_usage = 0.59
    status.mem_usage = 0.52
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
    lte.sig_level = 4
    lte.rsrp = -82
    lte.rsrq = -10
    lte.snr = 14
    lte.isp_name = "Bite"
    fake_lib.get_lte_status.return_value = lte

    active = _device("AA-BB-CC-DD-EE-01", "live", "1.1.1.1", "host_5g")
    inactive = _device("AA-BB-CC-DD-EE-02", "ghost", "1.1.1.2", "host_5g")
    inactive.active = False
    status = MagicMock()
    status.devices = [active, inactive]
    status.cpu_usage = 0.59
    status.mem_usage = 0.52
    fake_lib.get_status.return_value = status

    fake_lib.ActItem = MagicMock()
    fake_lib.ActItem.GL = "gl"
    fake_lib.req_act.return_value = ("raw", [[]])

    client = LibRouterClient(_lib=fake_lib)
    snap = client.snapshot()

    assert {c.mac for c in snap.clients} == {"AA:BB:CC:DD:EE:01"}


def test_snapshot_oserror_also_raises_connection_error():
    fake_lib = MagicMock()
    fake_lib.get_lte_status.side_effect = OSError("connection refused")

    client = LibRouterClient(_lib=fake_lib)
    with pytest.raises(ConnectionError):
        client.snapshot()


def test_snapshot_session_loss_triggers_auth_backoff_instead_of_reauth():
    """A non-network fetch failure means our session was kicked (likely Tether).
    The collector must NOT immediately re-authorise — that would just steal the
    session back from Tether — it should raise AuthError and arm a cooldown.
    """
    from tplinkrouterc6u.common.exception import ClientException

    fake_lib = MagicMock()
    fake_lib.get_lte_status.side_effect = ClientException("session lost")

    clock = iter([1000, 1001])
    client = LibRouterClient(
        _lib=fake_lib, auth_backoff_seconds=300, _now=lambda: next(clock),
    )
    with pytest.raises(AuthError) as exc:
        client.snapshot()
    assert exc.value.retry_after == 300

    # While the cooldown is active, snapshot() must short-circuit without
    # touching the router at all.
    fake_lib.reset_mock()
    fake_lib.get_lte_status.side_effect = ClientException("would not be called")
    with pytest.raises(AuthError) as exc:
        client.snapshot()
    assert exc.value.retry_after == 299
    fake_lib.authorize.assert_not_called()
    fake_lib.get_lte_status.assert_not_called()


def test_snapshot_oserror_does_not_arm_auth_backoff():
    """A socket-level failure is a network blip, not a session-kick. The
    collector should report it as ConnectionError and keep polling normally."""
    fake_lib = MagicMock()
    fake_lib.get_lte_status.side_effect = OSError("connection refused")

    client = LibRouterClient(_lib=fake_lib, auth_backoff_seconds=300)
    with pytest.raises(ConnectionError):
        client.snapshot()

    # No cooldown armed — next snapshot would still try to fetch, not
    # short-circuit with an AuthError.
    assert client._kicked_until is None


def test_snapshot_reclaims_session_after_backoff_elapses():
    """After the cooldown window the collector re-authorises once and
    resumes polling."""
    fake_lib = MagicMock()

    lte = MagicMock()
    lte.total_statistics = 100
    lte.cur_rx_speed = 50
    lte.cur_tx_speed = 25
    lte.sig_level = 4
    lte.isp_name = "Bite"

    status = MagicMock()
    status.devices = []
    status.cpu_usage = 0.0
    status.mem_usage = 0.0

    from tplinkrouterc6u.common.exception import ClientException
    fake_lib.get_lte_status.side_effect = [
        ClientException("kicked"),  # first snapshot fails → arms backoff
        lte,                         # reclaim succeeds
    ]
    fake_lib.get_status.return_value = status
    fake_lib.ActItem = MagicMock()
    fake_lib.ActItem.GL = "gl"
    fake_lib.req_act.return_value = ("raw", [[]])

    # Clock: 1000 = first snapshot (kick), 1301 = past the 300s cooldown.
    clock = iter([1000, 1301])
    client = LibRouterClient(
        _lib=fake_lib, auth_backoff_seconds=300, _now=lambda: next(clock),
    )

    with pytest.raises(AuthError):
        client.snapshot()

    # authorize was NOT called when we got kicked.
    fake_lib.authorize.assert_not_called()

    snap = client.snapshot()
    assert snap.total_bytes == 100
    fake_lib.authorize.assert_called_once()
    assert client._kicked_until is None


def test_reauth_after_backoff_failure_re_arms_cooldown():
    """If the reclaim re-auth still fails (Tether is still active), arm the
    cooldown again instead of busy-looping."""
    fake_lib = MagicMock()
    fake_lib.get_lte_status.side_effect = Exception("never reached")
    fake_lib.authorize.side_effect = [Exception("still kicked")]

    client = LibRouterClient(
        _lib=fake_lib, auth_backoff_seconds=300, _now=lambda: 2000,
    )
    client._kicked_until = 1000  # cooldown already elapsed

    with pytest.raises(AuthError) as exc:
        client.snapshot()
    assert exc.value.retry_after == 300
    assert client._kicked_until == 2300


def test_snapshot_carries_wan_status():
    fake_lib = MagicMock()
    lte = MagicMock()
    lte.total_statistics = 1
    lte.cur_rx_speed = 0
    lte.cur_tx_speed = 0
    lte.sig_level = 4
    lte.rsrp = -82
    lte.rsrq = -10
    lte.snr = 14
    lte.isp_name = "Bite"
    fake_lib.get_lte_status.return_value = lte

    status = MagicMock()
    status.devices = []
    status.cpu_usage = 0.59
    status.mem_usage = 0.52
    fake_lib.get_status.return_value = status

    fake_lib.ActItem = MagicMock()
    fake_lib.ActItem.GL = "gl"
    fake_lib.ActItem.GET = "go"
    # Three req_act calls: _fetch_stat_rows, _fetch_link_cfg, _fetch_serving_cells
    fake_lib.req_act.side_effect = [
        ("raw", [[]]),   # stat rows → empty
        ("raw", [[]]),   # link cfg → empty
        ("raw", [[]]),   # serving cells → no active cells
    ]

    client = LibRouterClient(_lib=fake_lib)
    snap = client.snapshot()

    assert snap.wan_status.sig_level == 4
    # rsrp/rsrq/snr now come from serving-cell data; empty → None
    assert snap.wan_status.rsrp is None
    assert snap.wan_status.isp_name == "Bite"
    assert snap.wan_status.cpu_pct == 0.59
    assert snap.wan_status.mem_pct == 0.52


def test_snapshot_includes_serving_cell_signal(monkeypatch):
    fake_lib = MagicMock()

    lte_status = MagicMock()
    lte_status.total_statistics = 1
    lte_status.cur_rx_speed = 0
    lte_status.cur_tx_speed = 0
    lte_status.sig_level = 0
    lte_status.rsrp = 0
    lte_status.rsrq = 0
    lte_status.snr = 0
    lte_status.isp_name = "Bite"
    fake_lib.get_lte_status.return_value = lte_status

    status = MagicMock()
    status.devices = []
    status.cpu_usage = 0.3
    status.mem_usage = 0.5
    fake_lib.get_status.return_value = status

    fake_lib.ActItem = MagicMock()
    fake_lib.ActItem.GL = "gl"
    fake_lib.ActItem.GET = "go"

    # Three req_act calls in order:
    #   1) DEV2_STAT_ENTRY  (clients) → empty
    #   2) DEV2_LTE_LINK_CFG          → link cfg dict
    #   3) DEV2_LTE_SERVING_CELL_INFO → list of cells
    fake_lib.req_act.side_effect = [
        ("raw", [[]]),
        ("raw", [{"connectedBand": "B3;N40", "endcStatus": "1", "networkType": "8",
                  "ipv4": "10.0.0.1", "ipv6": "2a00::1"}]),
        ("raw", [[
            {"networkType": "3", "cellConnectionStatus": "1", "band": "3",
             "RSRP": "-80", "RSRQ": "-17", "SNR": "60", "signalStrength": "3"},
            {"networkType": "8", "cellConnectionStatus": "1", "band": "40",
             "SSRSRP": "-74", "SSRSRQ": "-10", "SSSINR": "310",
             "signalStrength": "4"},
        ]]),
    ]

    client = LibRouterClient(_lib=fake_lib)
    snap = client.snapshot()

    assert snap.wan_status.rsrp == -80
    assert snap.wan_status.rsrq == -17
    assert snap.wan_status.snr == 60
    assert snap.wan_status.lte_signal_strength == 3
    assert snap.wan_status.lte_band == "3"
    assert snap.wan_status.ss_rsrp == -74
    assert snap.wan_status.ss_rsrq == -10
    assert snap.wan_status.ss_sinr == 310
    assert snap.wan_status.nr_signal_strength == 4
    assert snap.wan_status.nr_band == "40"
