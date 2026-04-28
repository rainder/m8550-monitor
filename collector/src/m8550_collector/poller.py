import logging
import time
from typing import Callable

from .rate import RateInputs, compute_rate
from .router import RouterClient
from .store import Store


log = logging.getLogger(__name__)


class Poller:
    def __init__(
        self,
        router: RouterClient,
        store: Store,
        now: Callable[[], int] = lambda: int(time.time()),
        max_gap_seconds: int = 10,
    ):
        self.router = router
        self.store = store
        self.now = now
        self.max_gap_seconds = max_gap_seconds

    def tick(self) -> None:
        ts = self.now()
        try:
            snap = self.router.snapshot()
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

    def run_forever(self, interval: int) -> None:
        """Poll forever. Use a longer sleep when the router is unreachable."""
        backoff_interval = max(interval * 6, 30)
        while True:
            self.tick()
            sample = self.store.latest_sample()
            sleep_for = interval if sample and sample["online"] else backoff_interval
            time.sleep(sleep_for)
