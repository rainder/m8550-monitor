import logging
import time
from typing import Callable

from .push import PushSubscription, VapidKeys, dispatch_sms_pushes
from .router import AuthError, RouterClient
from .store import Store


log = logging.getLogger(__name__)


class Poller:
    def __init__(
        self,
        router: RouterClient,
        store: Store,
        now: Callable[[], int] = lambda: int(time.time()),
        max_gap_seconds: int = 10,
        sms_poll_interval: int = 60,
        vapid_keys: VapidKeys | None = None,
    ):
        self.router = router
        self.store = store
        self.now = now
        self.max_gap_seconds = max_gap_seconds
        self.sms_poll_interval = sms_poll_interval
        self.vapid_keys = vapid_keys
        self._last_sms_fetch_ts = 0
        # MAC → (ts, cumulative_packets). Held in-memory; bandwidth is
        # ephemeral so we don't bother persisting it across collector restarts.
        self._last_packets: dict[str, tuple[int, int]] = {}

    def tick(self) -> None:
        ts = self.now()
        # If the user pressed "Reclaim session" in the UI, jump the backoff
        # and try to authorize right now — the snapshot below then has a
        # fresh session to work with.
        self._process_router_actions()
        try:
            snap = self.router.snapshot()
        except AuthError as e:
            log.warning("router auth: %s", e)
            self.store.append_sample(
                ts=ts, total_bytes=None,
                rx_rate=None, tx_rate=None, online=False,
            )
            return
        except ConnectionError as e:
            log.warning("router unreachable: %s", e)
            self.store.append_sample(
                ts=ts, total_bytes=None,
                rx_rate=None, tx_rate=None, online=False,
            )
            return

        # WAN totals + rates: rates are direct from the router, no delta math.
        self.store.append_sample(
            ts=ts,
            total_bytes=snap.total_bytes,
            rx_rate=snap.rx_rate,
            tx_rate=snap.tx_rate,
            online=True,
            wan_status=snap.wan_status,
        )

        # Per-client bandwidth: packet deltas × avg packet size.
        #
        # The router's DEV2_STAT_ENTRY.totalBytes per-client counter only
        # tracks connection-tracking metadata on M8550 firmware (under-counts
        # by ~1000× during bulk transfer), so we derive bandwidth from the
        # AP-association packet counters instead. To turn packets/sec back
        # into bytes/sec we estimate avg packet size from the WAN counter,
        # which IS accurate: avg = (rx_rate + tx_rate) / total_packets_per_sec.
        next_packets: dict[str, tuple[int, int]] = {}
        client_packet_rates: dict[str, int] = {}
        for c in snap.clients:
            if c.packets_total is None:
                continue
            next_packets[c.mac] = (ts, c.packets_total)
            prev = self._last_packets.get(c.mac)
            if prev is None:
                continue
            prev_ts, prev_packets = prev
            dt = ts - prev_ts
            if dt <= 0 or dt > self.max_gap_seconds:
                continue
            delta = c.packets_total - prev_packets
            if delta < 0:
                continue
            client_packet_rates[c.mac] = int(delta / dt)
        total_pps = sum(client_packet_rates.values())
        wan_bps = (snap.rx_rate or 0) + (snap.tx_rate or 0)
        avg_pkt_size = wan_bps / total_pps if total_pps > 0 else 0.0
        self._last_packets = next_packets

        client_rows: list[dict] = []
        for c in snap.clients:
            pps = client_packet_rates.get(c.mac)
            if pps is not None and avg_pkt_size > 0:
                bandwidth: int | None = int(pps * avg_pkt_size)
            else:
                bandwidth = None
            client_rows.append({
                "mac": c.mac,
                "name": c.name,
                "ip": c.ip,
                "conn_type": c.conn_type,
                "total_bytes": c.total_bytes,
                "bandwidth": bandwidth,
            })

        self.store.append_clients(ts=ts, clients=client_rows)

        # User-initiated SMS actions (mark-read, mark-all-read) sit in a
        # queue the web app populates. Process them eagerly — every tick —
        # so the UI feels snappy even though the inbox itself polls slower.
        self._process_sms_actions()

        # SMS — refresh on a slower cadence than the rate poll.
        if (
            self.sms_poll_interval > 0
            and ts - self._last_sms_fetch_ts >= self.sms_poll_interval
        ):
            try:
                messages = self.router.list_sms()
                new_messages = self.store.replace_sms(ts=ts, messages=messages)
                self._last_sms_fetch_ts = ts
                if new_messages and self.vapid_keys is not None:
                    self._push_new_sms(new_messages)
            except (AuthError, ConnectionError) as e:
                log.warning("sms fetch skipped: %s", e)
            except Exception:
                log.exception("sms fetch failed")

    def _process_router_actions(self) -> None:
        for a in self.store.pending_router_actions():
            try:
                if a["action"] == "reauth":
                    self.router.force_reauth()
                else:
                    log.warning("dropping unknown router action %r", a["action"])
            except Exception as e:
                # Drop the action regardless: the user can click again if
                # they still want a retry. Looping on a failed reauth would
                # only hide the underlying problem.
                log.warning("router action %s failed: %s", a["action"], e)
            self.store.delete_router_action(a["id"])

    def _process_sms_actions(self) -> None:
        actions = self.store.pending_sms_actions()
        for a in actions:
            sms_id = a["sms_id"]
            action = a["action"]
            try:
                if action == "mark_read":
                    ok = self.router.mark_sms_read(sms_id)
                    if ok:
                        self.store.mark_sms_read_local(sms_id)
                elif action == "mark_all_read":
                    self.router.mark_all_sms_read()
                    self.store.mark_all_sms_read_local()
                else:
                    log.warning("dropping unknown sms action %r for id=%s", action, sms_id)
                self.store.delete_sms_action(a["id"])
            except (AuthError, ConnectionError) as e:
                # Transient — keep the action queued and try next tick.
                log.warning("sms action %s id=%s deferred: %s", action, sms_id, e)
                return
            except Exception:
                log.exception("sms action %s id=%s failed; dropping", action, sms_id)
                self.store.delete_sms_action(a["id"])

    def _push_new_sms(self, new_messages) -> None:
        try:
            subs = [
                PushSubscription(endpoint=r["endpoint"], p256dh=r["p256dh"], auth=r["auth"])
                for r in self.store.list_push_subscriptions()
            ]
            if not subs:
                return
            log.info("dispatching push for %d new sms to %d subs",
                     len(new_messages), len(subs))
            assert self.vapid_keys is not None
            dead = dispatch_sms_pushes(new_messages, subs, self.vapid_keys)
            if dead:
                self.store.delete_push_subscriptions(dead)
        except Exception:
            log.exception("push dispatch failed")

    def run_forever(self, interval: int) -> None:
        """Poll forever. Use a longer sleep when the router is unreachable."""
        backoff_interval = max(interval * 6, 30)
        while True:
            try:
                self.tick()
            except Exception:
                log.exception("tick failed")
            sample = self.store.latest_sample()
            sleep_for = interval if sample and sample["online"] else backoff_interval
            time.sleep(sleep_for)
