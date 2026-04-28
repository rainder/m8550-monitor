from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class RouterClientSnapshot:
    """One reading for a single connected device."""
    mac: str
    name: str | None
    ip: str | None
    conn_type: str             # "host_2g" | "host_5g" | "wired"
    total_bytes: int           # cumulative combined RX+TX from DEV2_STAT_ENTRY


@dataclass(frozen=True)
class RouterSnapshot:
    """One whole-router reading. All values may be None when offline."""
    total_bytes: int | None    # WAN cumulative combined (total_statistics)
    rx_rate: int | None        # WAN bytes/sec down (cur_rx_speed)
    tx_rate: int | None        # WAN bytes/sec up (cur_tx_speed)
    clients: list[RouterClientSnapshot]


class RouterClient(Protocol):
    def snapshot(self) -> RouterSnapshot:
        """Authenticate if needed and return one reading.

        Raises ConnectionError on unreachable, AuthError on bad credentials.
        """
        ...


class AuthError(Exception):
    pass
