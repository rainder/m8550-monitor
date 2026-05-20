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

    client = LibRouterClient(_lib=fake_lib, stale_session_threshold=99)
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


def test_repeated_oserrors_trigger_self_heal_reauth():
    """Some session kicks surface as TCP resets (OSError) rather than 401s.
    After ``stale_session_threshold`` consecutive ConnectionErrors the
    client tries one re-auth+refetch to self-heal a stuck session.
    """
    fake_lib = MagicMock()

    lte = MagicMock()
    lte.total_statistics = 1; lte.cur_rx_speed = 0; lte.cur_tx_speed = 0
    lte.sig_level = 4; lte.isp_name = "Bite"
    status = MagicMock()
    status.devices = []; status.cpu_usage = 0; status.mem_usage = 0

    # Three OSErrors, then on the fourth call the threshold triggers
    # reauth + refetch which both succeed.
    fake_lib.get_lte_status.side_effect = [
        OSError("reset"), OSError("reset"), OSError("reset"),
        OSError("reset"),  # triggers reauth path
        lte,                # refetch after reauth succeeds
    ]
    fake_lib.get_status.return_value = status
    fake_lib.ActItem = MagicMock(); fake_lib.ActItem.GL = "gl"
    fake_lib.req_act.return_value = ("raw", [[]])

    client = LibRouterClient(
        _lib=fake_lib, stale_session_threshold=4, auth_backoff_seconds=300,
    )

    for _ in range(3):
        with pytest.raises(ConnectionError):
            client.snapshot()
    fake_lib.authorize.assert_not_called()

    snap = client.snapshot()
    assert snap.total_bytes == 1
    fake_lib.authorize.assert_called_once()
    # Counter reset after success.
    assert client._consecutive_oserrors == 0


def test_self_heal_reauth_failure_arms_auth_backoff():
    """If the threshold-triggered reauth attempt itself fails, fall back
    to the same 5-minute auth backoff the session-kick path uses."""
    fake_lib = MagicMock()
    fake_lib.get_lte_status.side_effect = OSError("reset")
    fake_lib.authorize.side_effect = Exception("router refusing auth")

    client = LibRouterClient(
        _lib=fake_lib,
        stale_session_threshold=2,
        auth_backoff_seconds=300,
        _now=lambda: 1000,
    )

    with pytest.raises(ConnectionError):
        client.snapshot()
    with pytest.raises(AuthError) as exc:
        client.snapshot()
    assert exc.value.retry_after == 300
    assert client._kicked_until == 1300
    fake_lib.authorize.assert_called_once()


def test_successful_snapshot_resets_oserror_counter():
    """A successful poll between failures resets the threshold counter so
    a new run of failures has to build up again."""
    fake_lib = MagicMock()

    lte = MagicMock()
    lte.total_statistics = 1; lte.cur_rx_speed = 0; lte.cur_tx_speed = 0
    lte.sig_level = 4; lte.isp_name = "Bite"
    status = MagicMock()
    status.devices = []; status.cpu_usage = 0; status.mem_usage = 0

    fake_lib.get_lte_status.side_effect = [
        OSError("reset"), OSError("reset"),
        lte,  # success → counter resets
        OSError("reset"),
    ]
    fake_lib.get_status.return_value = status
    fake_lib.ActItem = MagicMock(); fake_lib.ActItem.GL = "gl"
    fake_lib.req_act.return_value = ("raw", [[]])

    client = LibRouterClient(_lib=fake_lib, stale_session_threshold=4)
    with pytest.raises(ConnectionError): client.snapshot()
    with pytest.raises(ConnectionError): client.snapshot()
    client.snapshot()  # success
    with pytest.raises(ConnectionError): client.snapshot()
    # Reauth must NOT have triggered — the success reset the counter.
    fake_lib.authorize.assert_not_called()


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


def test_list_sms_aggregates_all_pages():
    """The M8550 paginates SMS at 8 per page. Earlier code only fetched page 1
    via ``attrs=['PageNumber=1']``, but the EX-firmware request serializer
    quotes any attr that lacks ``:`` as ``"PageNumber=1":""`` (a malformed
    key), so the SET silently fails and the router returns whichever page it
    happens to be on. list_sms() must walk pages with a properly JSON-
    formatted attr and stop when an empty page is returned.
    """
    fake_lib = MagicMock()
    fake_lib.ActItem = MagicMock()
    fake_lib.ActItem.SET = "so"
    fake_lib.ActItem.GL = "gl"

    def _row(idx, content="hi", unread="0"):
        return {
            "index": str(idx),
            "from": "LABAS",
            "content": content,
            "receivedTime": f"2026-02-{(idx % 28) + 1:02d} 10:00:00",
            "unread": unread,
        }

    page1 = [_row(i) for i in range(11, 19)]                   # 8 rows
    page2 = [_row(i) for i in range(3, 11)]                    # 8 rows
    page3 = [_row(i, content="Test", unread="1") for i in (1, 2)]  # 2 rows, one unread
    # Each Python-level req_act call returns the result of ONE iteration
    # (SET + GL bundled). The SET response has no "data" field so only the GL
    # list ends up in `values`.
    fake_lib.req_act.side_effect = [
        ("raw", [page1]),
        ("raw", [page2]),
        ("raw", [page3]),
        ("raw", [[]]),    # empty page → terminate
    ]

    client = LibRouterClient(_lib=fake_lib)
    msgs = client.list_sms()

    assert [m.id for m in msgs] == (
        [i for i in range(11, 19)] + [i for i in range(3, 11)] + [1, 2]
    )
    assert sum(1 for m in msgs if m.unread) == 2
    # SET attrs must contain a colon so the upstream EX serializer leaves the
    # JSON intact instead of wrapping it as a malformed key.
    set_calls = [
        c for c in fake_lib.ActItem.call_args_list
        if c.args and c.args[0] == "so"
    ]
    assert set_calls, "expected SET ActItems to be created"
    for call in set_calls:
        assert any(":" in a for a in call.kwargs.get("attrs", [])), (
            f"SET attrs missing colon-formatted PageNumber: {call.kwargs}"
        )


def test_mark_sms_read_locates_slot_then_sets_unread_zero():
    """The router-side slot of an SMS depends on which page it's on, and slots
    shift when other messages are deleted. The client must walk pages to
    locate the target's (page, slot), then SET unread=0 against that slot
    using the JSON-quoted attr that survives the EX serializer."""
    fake_lib = MagicMock()
    fake_lib.ActItem = MagicMock()
    fake_lib.ActItem.SET = "so"
    fake_lib.ActItem.GL = "gl"
    fake_lib.ActItem.DEL = "del"

    page1 = [{"index": "25"}, {"index": "24"}, {"index": "23"}]
    page2 = [{"index": "10"}, {"index": "9"}, {"index": "8"}, {"index": "7"}]
    # locate() consumes one req_act per page until it finds id=8 on page 2,
    # then mark_sms_read() makes one more req_act for the SET.
    fake_lib.req_act.side_effect = [
        ("raw", [page1]),
        ("raw", [page2]),
        ("raw", [[]]),  # SET response — no data field, locate doesn't reach
    ]

    client = LibRouterClient(_lib=fake_lib)
    assert client.mark_sms_read(8) is True

    # Inspect the final req_act call — it must SET the target page first then
    # SET unread=0 at the located slot (id=8 is the 3rd row on page 2).
    final_call = fake_lib.req_act.call_args_list[-1]
    acts = final_call.args[0]
    assert len(acts) == 2
    set_page_call, set_unread_call = (
        fake_lib.ActItem.call_args_list[-2],
        fake_lib.ActItem.call_args_list[-1],
    )
    assert set_page_call.args == ("so", "DEV2_LTE_SMS_RECVMSGBOX")
    assert any('"PageNumber":"2"' in a for a in set_page_call.kwargs["attrs"])
    assert set_unread_call.args == ("so", "DEV2_LTE_SMS_RECVMSGENTRY", "3,0,0,0,0,0")
    assert any('"unread":"0"' in a for a in set_unread_call.kwargs["attrs"])


def test_mark_sms_read_returns_false_when_message_not_found():
    fake_lib = MagicMock()
    fake_lib.ActItem = MagicMock()
    fake_lib.ActItem.SET = "so"
    fake_lib.ActItem.GL = "gl"
    fake_lib.req_act.side_effect = [
        ("raw", [[{"index": "1"}]]),
        ("raw", [[]]),  # second page empty → end of walk
    ]
    client = LibRouterClient(_lib=fake_lib)
    assert client.mark_sms_read(99) is False
    # No SET-unread should have happened.
    set_unread_calls = [
        c for c in fake_lib.ActItem.call_args_list
        if c.args and c.args[0] == "so" and len(c.args) >= 2
        and c.args[1] == "DEV2_LTE_SMS_RECVMSGENTRY"
    ]
    assert set_unread_calls == []


def test_list_sms_stops_after_max_pages_on_repeating_router():
    """Defensive: if the router ignores PageNumber and keeps returning the
    same page (older firmware behaviour we observed pre-fix), iteration must
    still terminate rather than loop forever. Dedup by id should cause the
    second page-of-already-seen-ids to break the loop.
    """
    fake_lib = MagicMock()
    fake_lib.ActItem = MagicMock()
    fake_lib.ActItem.SET = "so"
    fake_lib.ActItem.GL = "gl"

    same_page = [
        {"index": "1", "from": "X", "content": "a",
         "receivedTime": "2026-02-20 10:00:00", "unread": "0"},
    ]
    # 60 identical responses — well past any sane page cap.
    fake_lib.req_act.side_effect = [("raw", [same_page])] * 60

    client = LibRouterClient(_lib=fake_lib)
    msgs = client.list_sms()

    assert [m.id for m in msgs] == [1]
    assert fake_lib.req_act.call_count < 60
