import sqlite3

import pytest

from m8550_collector.poller import Poller
from m8550_collector.router import (
    AuthError, RouterSnapshot, RouterClientSnapshot, SmsMessage, WanStatus,
)
from m8550_collector.store import Store


def _wan_idle() -> WanStatus:
    """A WanStatus with all-None fields, for tests that don't care."""
    return WanStatus(sig_level=None, rsrp=None, rsrq=None, snr=None,
                     isp_name=None, cpu_pct=None, mem_pct=None,
                     connected_band=None, endc_status=None, network_type=None,
                     wan_ipv4=None, wan_ipv6=None,
                     ss_rsrp=None, ss_rsrq=None, ss_sinr=None,
                     nr_signal_strength=None, nr_band=None,
                     lte_signal_strength=None, lte_band=None)


class FakeRouter:
    def __init__(self, snapshots, sms=None):
        self.snapshots = list(snapshots)
        self.sms = sms if sms is not None else []
        self.sms_calls = 0
        self.mark_calls: list[int] = []
        self.reauth_calls = 0
        self.reauth_result: object = True
        # Per-id behaviour overrides — set to bool to short-circuit or to an
        # Exception to raise. Default is "id present → True".
        self.mark_result: dict[int, object] = {}

    def force_reauth(self) -> bool:
        self.reauth_calls += 1
        if isinstance(self.reauth_result, Exception):
            raise self.reauth_result
        return bool(self.reauth_result)

    def snapshot(self):
        if not self.snapshots:
            raise ConnectionError("no more snapshots")
        s = self.snapshots.pop(0)
        if isinstance(s, Exception):
            raise s
        return s

    def list_sms(self):
        self.sms_calls += 1
        if isinstance(self.sms, Exception):
            raise self.sms
        return list(self.sms)

    def mark_sms_read(self, message_id: int) -> bool:
        self.mark_calls.append(message_id)
        result = self.mark_result.get(message_id, True)
        if isinstance(result, Exception):
            raise result
        return bool(result)


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
                    conn_type="host_5g", total_bytes=500_000, packets_total=100,
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


def test_second_tick_scales_packets_by_wan_derived_avg(tmp_path):
    """Bandwidth = packets/sec × (WAN B/s ÷ total client packets/sec). With
    a single client carrying all the traffic, its bandwidth should equal the
    WAN rate. Verifies the dynamic-avg-packet-size scaling that replaced the
    old (broken) total_bytes-derived calculation."""
    store = _store(tmp_path)
    router = FakeRouter([
        RouterSnapshot(
            total_bytes=10_000, rx_rate=900, tx_rate=100,
            wan_status=_wan_idle(),
            clients=[
                RouterClientSnapshot(
                    mac="aa", name="phone", ip="1.1.1.1",
                    conn_type="host_5g", total_bytes=500_000, packets_total=0,
                ),
            ],
        ),
        RouterSnapshot(
            total_bytes=15_000, rx_rate=900, tx_rate=100,
            wan_status=_wan_idle(),
            clients=[
                RouterClientSnapshot(
                    mac="aa", name="phone", ip="1.1.1.1",
                    conn_type="host_5g", total_bytes=500_500, packets_total=10,
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
    # 10 packets over 5s = 2 pps. WAN total = 1000 B/s. avg = 500 B/pkt.
    # Single client → it gets the whole WAN: 2 pps × 500 B/pkt = 1000 B/s.
    assert row == (1000,)

    sample = store.latest_sample()
    assert sample["rx_rate"] == 900
    assert sample["tx_rate"] == 100


def test_bandwidth_splits_proportional_to_packet_share(tmp_path):
    """Two active clients carrying the same WAN: each gets a share of WAN B/s
    proportional to its share of packets/sec."""
    store = _store(tmp_path)
    router = FakeRouter([
        RouterSnapshot(
            total_bytes=0, rx_rate=900, tx_rate=100,
            wan_status=_wan_idle(),
            clients=[
                RouterClientSnapshot(mac="aa", name=None, ip=None,
                                     conn_type="host_5g", total_bytes=0, packets_total=0),
                RouterClientSnapshot(mac="bb", name=None, ip=None,
                                     conn_type="host_5g", total_bytes=0, packets_total=0),
            ],
        ),
        RouterSnapshot(
            total_bytes=5000, rx_rate=900, tx_rate=100,
            wan_status=_wan_idle(),
            clients=[
                # 3:1 packet share across 5s → avg = 1000 / (4 pps) = 250 B/pkt
                RouterClientSnapshot(mac="aa", name=None, ip=None,
                                     conn_type="host_5g", total_bytes=0, packets_total=15),
                RouterClientSnapshot(mac="bb", name=None, ip=None,
                                     conn_type="host_5g", total_bytes=0, packets_total=5),
            ],
        ),
    ])
    clock = iter([100, 105])
    p = Poller(router, store, now=lambda: next(clock))
    p.tick(); p.tick()

    conn = sqlite3.connect(store.path)
    rows = dict(conn.execute(
        "SELECT mac, bandwidth FROM clients WHERE ts = 105"
    ).fetchall())
    # avg packet size = 1000 / 4 = 250 B/pkt
    # aa: 3 pps × 250 = 750 B/s   bb: 1 pps × 250 = 250 B/s
    assert rows == {"aa": 750, "bb": 250}


def test_wired_client_without_packet_counter_yields_null_bandwidth(tmp_path):
    """DEV2_ADT_WIFI_CLIENT only lists Wi-Fi clients; a wired client lacks a
    packets_total. The poller must record the row but leave bandwidth None
    rather than misattributing WAN traffic to it."""
    store = _store(tmp_path)
    router = FakeRouter([
        RouterSnapshot(
            total_bytes=0, rx_rate=1000, tx_rate=0,
            wan_status=_wan_idle(),
            clients=[RouterClientSnapshot(mac="aa", name=None, ip=None,
                                          conn_type="wired",
                                          total_bytes=100, packets_total=None)],
        ),
        RouterSnapshot(
            total_bytes=5000, rx_rate=1000, tx_rate=0,
            wan_status=_wan_idle(),
            clients=[RouterClientSnapshot(mac="aa", name=None, ip=None,
                                          conn_type="wired",
                                          total_bytes=200, packets_total=None)],
        ),
    ])
    clock = iter([100, 105])
    p = Poller(router, store, now=lambda: next(clock))
    p.tick(); p.tick()

    conn = sqlite3.connect(store.path)
    row = conn.execute("SELECT bandwidth FROM clients WHERE ts = 105").fetchone()
    assert row == (None,)


def test_per_client_counter_reset_yields_null_bandwidth(tmp_path):
    """If the router-side packet counter drops between ticks (router reboot,
    client reassociation, MAC change), we must report None rather than a
    nonsense negative-derived rate."""
    store = _store(tmp_path)
    router = FakeRouter([
        RouterSnapshot(
            total_bytes=10, rx_rate=1000, tx_rate=0,
            wan_status=_wan_idle(),
            clients=[RouterClientSnapshot(mac="aa", name=None, ip=None,
                                          conn_type="host_5g",
                                          total_bytes=500, packets_total=500)],
        ),
        RouterSnapshot(
            total_bytes=20, rx_rate=1000, tx_rate=0,
            wan_status=_wan_idle(),
            clients=[RouterClientSnapshot(mac="aa", name=None, ip=None,
                                          conn_type="host_5g",
                                          total_bytes=10, packets_total=10)],
        ),
    ])
    clock = iter([100, 105])
    p = Poller(router, store, now=lambda: next(clock))

    p.tick()
    p.tick()

    conn = sqlite3.connect(store.path)
    row = conn.execute("SELECT bandwidth FROM clients WHERE ts = 105").fetchone()
    assert row == (None,)


def test_per_client_packet_counter_disappears_yields_null_bandwidth(tmp_path):
    """Tick 1: client has packets_total=1000. Tick 2: same MAC,
    packets_total=None (Wi-Fi client dropped out of DEV2_ADT_WIFI_CLIENT
    but still in DEV2_STAT_ENTRY). Must NOT crash; bandwidth at tick 2 is
    None."""
    store = _store(tmp_path)
    router = FakeRouter([
        RouterSnapshot(
            total_bytes=10, rx_rate=1000, tx_rate=0,
            wan_status=_wan_idle(),
            clients=[RouterClientSnapshot(
                mac="aa", name=None, ip=None,
                conn_type="host_5g", total_bytes=500_000, packets_total=1000,
            )],
        ),
        RouterSnapshot(
            total_bytes=20, rx_rate=1000, tx_rate=0,
            wan_status=_wan_idle(),
            clients=[RouterClientSnapshot(
                mac="aa", name=None, ip=None,
                conn_type="host_5g", total_bytes=None, packets_total=None,
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


def test_auth_error_writes_offline_row(tmp_path):
    """Session contention (kicked by Tether) shows as offline, same as
    network unreachable — the dashboard's status pill flips to offline and
    the collector stops trying for a while."""
    store = _store(tmp_path)
    router = FakeRouter([AuthError("kicked by tether", retry_after=300)])
    p = Poller(router, store, now=lambda: 100)

    p.tick()

    sample = store.latest_sample()
    assert sample == {
        "ts": 100, "total_bytes": None,
        "rx_rate": None, "tx_rate": None,
        "online": False,
    }


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


class FakePushBus:
    def __init__(self):
        self.calls: list[tuple[int, list]] = []

    def __call__(self, new_messages, subs, keys):
        self.calls.append((len(subs), list(new_messages)))
        return []  # no dead


def iter_clock(values):
    it = iter(values)
    return lambda: next(it)


def test_poller_fetches_sms_on_first_tick(tmp_path):
    store = _store(tmp_path)
    sms = [
        SmsMessage(id=8, sender="LABAS", content="hi", received_at=1700, unread=False),
        SmsMessage(id=9, sender="SHORT", content="unread one", received_at=1800, unread=True),
    ]
    router = FakeRouter(
        [RouterSnapshot(total_bytes=1, rx_rate=0, tx_rate=0,
                        wan_status=_wan_idle(), clients=[], sms_unread_count=1)],
        sms=sms,
    )
    p = Poller(router, store, now=lambda: 100, sms_poll_interval=60)
    p.tick()

    rows = store.list_sms()
    assert [(r["id"], r["sender"], r["unread"]) for r in rows] == [
        (9, "SHORT", True), (8, "LABAS", False),  # sorted DESC by received_at
    ]
    assert router.sms_calls == 1


def test_poller_skips_sms_until_interval_elapses(tmp_path):
    store = _store(tmp_path)
    router = FakeRouter(
        [
            RouterSnapshot(total_bytes=1, rx_rate=0, tx_rate=0,
                           wan_status=_wan_idle(), clients=[]),
            RouterSnapshot(total_bytes=2, rx_rate=0, tx_rate=0,
                           wan_status=_wan_idle(), clients=[]),
            RouterSnapshot(total_bytes=3, rx_rate=0, tx_rate=0,
                           wan_status=_wan_idle(), clients=[]),
        ],
        sms=[SmsMessage(id=1, sender="X", content="", received_at=0, unread=False)],
    )
    clock = iter([100, 130, 165])
    p = Poller(router, store, now=lambda: next(clock), sms_poll_interval=60)
    p.tick()  # 100 — first ever, fetch
    p.tick()  # 130 — only 30s elapsed, skip
    p.tick()  # 165 — 65s since first fetch, fetch
    assert router.sms_calls == 2


def test_poller_sms_disabled_when_interval_zero(tmp_path):
    store = _store(tmp_path)
    router = FakeRouter(
        [RouterSnapshot(total_bytes=1, rx_rate=0, tx_rate=0,
                        wan_status=_wan_idle(), clients=[])],
        sms=[SmsMessage(id=1, sender="X", content="", received_at=0, unread=False)],
    )
    p = Poller(router, store, now=lambda: 100, sms_poll_interval=0)
    p.tick()
    assert router.sms_calls == 0
    assert store.list_sms() == []


def test_poller_sms_fetch_failure_does_not_kill_tick(tmp_path):
    store = _store(tmp_path)
    router = FakeRouter(
        [RouterSnapshot(total_bytes=1, rx_rate=0, tx_rate=0,
                        wan_status=_wan_idle(), clients=[])],
        sms=ConnectionError("router blip"),
    )
    p = Poller(router, store, now=lambda: 100, sms_poll_interval=60)
    p.tick()  # must not raise; main sample still recorded
    sample = store.latest_sample()
    assert sample is not None and sample["online"] is True


def test_poller_dispatches_push_for_new_sms(tmp_path, monkeypatch):
    """A push fires only for SMS ids that weren't in the cache before — and
    only after the first sync (so we don't notify on the existing backlog
    when a user first installs the feature)."""
    from m8550_collector import poller as poller_mod
    from m8550_collector.push import VapidKeys

    bus = FakePushBus()
    monkeypatch.setattr(poller_mod, "dispatch_sms_pushes", bus)

    store = _store(tmp_path)
    store.add_push_subscription("ep1", "p", "a", created_at=0)

    fixed_keys = VapidKeys(public="P", private="K", subject="mailto:t@t")
    snap = lambda: RouterSnapshot(total_bytes=1, rx_rate=0, tx_rate=0,
                                  wan_status=_wan_idle(), clients=[])

    initial_sms = [SmsMessage(id=1, sender="A", content="x", received_at=10, unread=False)]
    new_arrival = initial_sms + [
        SmsMessage(id=2, sender="B", content="y", received_at=20, unread=True),
    ]
    router = FakeRouter([snap(), snap()], sms=initial_sms)
    p = Poller(router, store, now=iter_clock([100, 200]),
               sms_poll_interval=60, vapid_keys=fixed_keys)

    # First sync: cache was empty → no push, even though there's 1 message.
    p.tick()
    assert bus.calls == []

    # Second sync: simulate id=2 arriving. Only the new id triggers a push.
    router.sms = new_arrival
    p.tick()
    assert len(bus.calls) == 1
    sub_count, dispatched = bus.calls[0]
    assert sub_count == 1
    assert [m.id for m in dispatched] == [2]


def test_poller_does_not_dispatch_when_vapid_keys_absent(tmp_path, monkeypatch):
    from m8550_collector import poller as poller_mod
    bus = FakePushBus()
    monkeypatch.setattr(poller_mod, "dispatch_sms_pushes", bus)

    store = _store(tmp_path)
    store.add_push_subscription("ep1", "p", "a", created_at=0)
    snap = lambda: RouterSnapshot(total_bytes=1, rx_rate=0, tx_rate=0,
                                  wan_status=_wan_idle(), clients=[])
    sms1 = [SmsMessage(id=1, sender="A", content="x", received_at=10, unread=False)]
    sms2 = sms1 + [SmsMessage(id=2, sender="B", content="y", received_at=20, unread=True)]

    router = FakeRouter([snap(), snap()], sms=sms1)
    p = Poller(router, store, now=iter_clock([100, 200]),
               sms_poll_interval=60, vapid_keys=None)
    p.tick()
    router.sms = sms2
    p.tick()
    assert bus.calls == []


def test_tick_processes_queued_mark_read_action(tmp_path):
    store = _store(tmp_path)
    store.replace_sms(ts=100, messages=[
        SmsMessage(id=25, sender="X", content="t", received_at=10, unread=True),
    ])
    store.enqueue_sms_action(sms_id=25, action="mark_read", created_at=200)

    router = FakeRouter([
        RouterSnapshot(total_bytes=1, rx_rate=0, tx_rate=0,
                       wan_status=_wan_idle(), clients=[]),
    ])
    p = Poller(router, store, now=lambda: 300, sms_poll_interval=0)
    p.tick()

    assert router.mark_calls == [25]
    assert store.pending_sms_actions() == []
    assert store.list_sms()[0]["unread"] is False


def test_tick_processes_queued_delete_action(tmp_path):
    """Delete is a local soft-hide — the firmware doesn't support a real
    router-side delete, so the message stays in the router inbox but our
    list_sms() filters it out."""
    store = _store(tmp_path)
    store.replace_sms(ts=100, messages=[
        SmsMessage(id=25, sender="X", content="t", received_at=10, unread=False),
        SmsMessage(id=24, sender="Y", content="u", received_at=11, unread=False),
    ])
    store.enqueue_sms_action(sms_id=25, action="delete", created_at=200)

    router = FakeRouter([
        RouterSnapshot(total_bytes=1, rx_rate=0, tx_rate=0,
                       wan_status=_wan_idle(), clients=[]),
    ])
    p = Poller(router, store, now=lambda: 300, sms_poll_interval=0)
    p.tick()

    assert [r["id"] for r in store.list_sms()] == [24]
    assert store.pending_sms_actions() == []


def test_tick_delete_action_does_not_call_router(tmp_path):
    """Soft-hide is local-only — no router round-trip, so it can't be
    deferred by a router blip."""
    store = _store(tmp_path)
    store.replace_sms(ts=100, messages=[
        SmsMessage(id=25, sender="X", content="t", received_at=10, unread=False),
    ])
    store.enqueue_sms_action(sms_id=25, action="delete", created_at=200)

    # No snapshots queued — but the tick should still finish action
    # processing because the snapshot happens first; if it succeeds we proceed.
    router = FakeRouter([
        RouterSnapshot(total_bytes=1, rx_rate=0, tx_rate=0,
                       wan_status=_wan_idle(), clients=[]),
    ])
    router.mark_result[25] = ConnectionError("would only matter for mark_read")
    p = Poller(router, store, now=lambda: 300, sms_poll_interval=0)
    p.tick()

    assert store.list_sms() == []
    assert router.mark_calls == []  # mark wasn't requested


def test_tick_skips_local_change_when_router_says_message_gone(tmp_path):
    """If the router has already lost the message (returns False from the
    action), we still consume the queue entry but leave the local cache
    untouched — the next full SMS poll will reconcile it."""
    store = _store(tmp_path)
    store.replace_sms(ts=100, messages=[
        SmsMessage(id=25, sender="X", content="t", received_at=10, unread=True),
    ])
    store.enqueue_sms_action(sms_id=25, action="mark_read", created_at=200)

    router = FakeRouter([
        RouterSnapshot(total_bytes=1, rx_rate=0, tx_rate=0,
                       wan_status=_wan_idle(), clients=[]),
    ])
    router.mark_result[25] = False
    p = Poller(router, store, now=lambda: 300, sms_poll_interval=0)
    p.tick()

    assert store.pending_sms_actions() == []
    assert store.list_sms()[0]["unread"] is True


def test_tick_keeps_action_queued_when_router_unreachable(tmp_path):
    """Transient ConnectionError on mark_read must not drop the action — it
    sits in the queue and is retried next tick. Later actions stay pending so
    order is preserved (even local-hide deletes wait their turn)."""
    store = _store(tmp_path)
    store.replace_sms(ts=100, messages=[
        SmsMessage(id=25, sender="X", content="t", received_at=10, unread=True),
        SmsMessage(id=24, sender="Y", content="u", received_at=11, unread=False),
    ])
    a1 = store.enqueue_sms_action(sms_id=25, action="mark_read", created_at=200)
    a2 = store.enqueue_sms_action(sms_id=24, action="delete",    created_at=201)

    router = FakeRouter([
        RouterSnapshot(total_bytes=1, rx_rate=0, tx_rate=0,
                       wan_status=_wan_idle(), clients=[]),
        RouterSnapshot(total_bytes=2, rx_rate=0, tx_rate=0,
                       wan_status=_wan_idle(), clients=[]),
    ])
    router.mark_result[25] = ConnectionError("router blip")
    p = Poller(router, store, now=lambda: 300, sms_poll_interval=0)
    p.tick()

    assert [a["id"] for a in store.pending_sms_actions()] == [a1, a2]
    assert {r["id"] for r in store.list_sms()} == {25, 24}  # nothing hidden yet

    # Next tick: router recovered → mark_read completes, then the queued
    # delete soft-hides id=24 locally.
    del router.mark_result[25]
    p.tick()
    assert router.mark_calls == [25, 25]  # first call was the blip
    assert store.pending_sms_actions() == []
    assert [r["id"] for r in store.list_sms()] == [25]  # 24 hidden


def test_tick_drops_mark_read_action_on_non_transient_failure(tmp_path):
    """A non-network exception (bad data, library bug, etc.) shouldn't loop
    forever — log it and consume the queue entry."""
    store = _store(tmp_path)
    store.replace_sms(ts=100, messages=[
        SmsMessage(id=25, sender="X", content="t", received_at=10, unread=True),
    ])
    store.enqueue_sms_action(sms_id=25, action="mark_read", created_at=200)

    router = FakeRouter([
        RouterSnapshot(total_bytes=1, rx_rate=0, tx_rate=0,
                       wan_status=_wan_idle(), clients=[]),
    ])
    router.mark_result[25] = RuntimeError("library blew up")
    p = Poller(router, store, now=lambda: 300, sms_poll_interval=0)
    p.tick()

    assert store.pending_sms_actions() == []
    assert store.list_sms()[0]["unread"] is True  # local cache untouched


def test_tick_processes_pending_reauth_action_before_snapshot(tmp_path):
    """A queued 'reauth' action signals the user closed Tether (or whatever was
    holding the session) and wants the collector to reclaim NOW instead of
    waiting out the 60s backoff. The poller must call force_reauth() before
    the normal snapshot path and consume the queue entry exactly once."""
    store = _store(tmp_path)
    store.enqueue_router_action(action="reauth", created_at=200)

    router = FakeRouter([
        RouterSnapshot(total_bytes=1, rx_rate=0, tx_rate=0,
                       wan_status=_wan_idle(), clients=[]),
    ])
    p = Poller(router, store, now=lambda: 300, sms_poll_interval=0)
    p.tick()

    assert router.reauth_calls == 1
    assert store.pending_router_actions() == []


def test_tick_drops_reauth_action_even_when_reclaim_fails(tmp_path):
    """If force_reauth raises (router unreachable or still kicked), we still
    consume the queue entry — the user can click again. Looping on the same
    failed action would mask the underlying issue."""
    store = _store(tmp_path)
    store.enqueue_router_action(action="reauth", created_at=200)

    router = FakeRouter([
        RouterSnapshot(total_bytes=1, rx_rate=0, tx_rate=0,
                       wan_status=_wan_idle(), clients=[]),
    ])
    router.reauth_result = AuthError("still kicked")
    p = Poller(router, store, now=lambda: 300, sms_poll_interval=0)
    p.tick()  # must not raise

    assert router.reauth_calls == 1
    assert store.pending_router_actions() == []


def test_poller_persists_wan_status(tmp_path):
    store = _store(tmp_path)
    router = FakeRouter([
        RouterSnapshot(
            total_bytes=10_000, rx_rate=100, tx_rate=50,
            wan_status=WanStatus(sig_level=4, rsrp=-82, rsrq=-10, snr=14,
                                  isp_name="Bite", cpu_pct=0.59, mem_pct=0.52,
                                  connected_band="B3;N40", endc_status=1,
                                  network_type=8, wan_ipv4="10.0.0.1",
                                  wan_ipv6=None,
                                  ss_rsrp=None, ss_rsrq=None, ss_sinr=None,
                                  nr_signal_strength=None, nr_band=None,
                                  lte_signal_strength=None, lte_band=None),
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
