import logging
import time
from typing import Callable

from .push import PushSubscription, VapidKeys, dispatch_sms_pushes
from .rate import RateInputs, compute_rate
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

    def tick(self) -> None:
        ts = self.now()
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

        # Per-client bandwidth: derive from cumulative deltas.
        prev_totals = self.store.last_client_totals()
        client_rows: list[dict] = []
        for c in snap.clients:
            prev = prev_totals.get(c.mac)
            bandwidth = compute_rate(
                RateInputs(
                    prev_ts=prev[0] if prev else None,
                    prev_total=prev[1] if prev else None,
                    ts=ts,
                    total=c.total_bytes,
                ),
                max_gap_seconds=self.max_gap_seconds,
            )
            client_rows.append({
                "mac": c.mac,
                "name": c.name,
                "ip": c.ip,
                "conn_type": c.conn_type,
                "total_bytes": c.total_bytes,
                "bandwidth": bandwidth,
            })

        self.store.append_clients(ts=ts, clients=client_rows)

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
