from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class RouterClientSnapshot:
    """One reading for a single connected device."""
    mac: str
    name: str | None
    ip: str | None
    conn_type: str             # "host_2g" | "host_5g" | "wired"
    total_bytes: int | None    # cumulative combined RX+TX from DEV2_STAT_ENTRY; None if no stat row


@dataclass(frozen=True)
class WanStatus:
    """Signal, ISP, and system-resource fields from get_lte_status / get_status."""
    sig_level: int | None
    rsrp: int | None
    rsrq: int | None
    snr: int | None
    isp_name: str | None
    cpu_pct: float | None
    mem_pct: float | None


@dataclass(frozen=True)
class RouterSnapshot:
    """One whole-router reading. All values may be None when offline."""
    total_bytes: int | None    # WAN cumulative combined (total_statistics)
    rx_rate: int | None        # WAN bytes/sec down (cur_rx_speed)
    tx_rate: int | None        # WAN bytes/sec up (cur_tx_speed)
    wan_status: WanStatus
    clients: list[RouterClientSnapshot]


class RouterClient(Protocol):
    def snapshot(self) -> RouterSnapshot:
        """Authenticate if needed and return one reading.

        Raises ConnectionError on unreachable, AuthError on bad credentials.
        """
        ...


class AuthError(Exception):
    pass


import logging

log = logging.getLogger(__name__)


def _normalise_mac(mac: str) -> str:
    """Upper-case, colon-separated."""
    return mac.upper().replace("-", ":")


def _safe_int(v) -> int | None:
    try:
        return int(v) if v is not None else None
    except (TypeError, ValueError):
        return None


def _safe_float(v) -> float | None:
    try:
        return float(v) if v is not None else None
    except (TypeError, ValueError):
        return None


class LibRouterClient:
    """Adapter from tplinkrouterc6u (M8550 / TPLinkEXClient) to RouterClient."""

    def __init__(self, host: str = "", password: str = "", _lib=None):
        if _lib is not None:
            self._lib = _lib
            return
        from tplinkrouterc6u import TplinkRouterProvider
        self._lib = TplinkRouterProvider.get_client(
            host, password, username="user", logger=log,
        )
        self._lib.authorize()

    def snapshot(self) -> RouterSnapshot:
        try:
            lte, status, stat_rows = self._fetch_all()
        except (OSError, Exception) as first:
            # Session likely expired (M8550 invalidates other sessions when
            # the Tether app logs in, and ages out idle sessions). Re-auth
            # and try once more before giving up.
            try:
                self._lib.authorize()
                lte, status, stat_rows = self._fetch_all()
            except Exception as retry:
                raise ConnectionError(f"{first}; reauth retry: {retry}") from retry

        clients: list[RouterClientSnapshot] = []
        for d in status.devices:
            if not getattr(d, "active", True):
                continue
            mac = _normalise_mac(str(d._macaddr))
            total = stat_rows.get(mac)
            clients.append(
                RouterClientSnapshot(
                    mac=mac,
                    name=d.hostname or None,
                    ip=str(d._ipaddr) if d._ipaddr is not None else None,
                    conn_type=d.type.value,
                    total_bytes=total,
                )
            )

        wan_status = WanStatus(
            sig_level=_safe_int(getattr(lte, "sig_level", None)),
            rsrp=_safe_int(getattr(lte, "rsrp", None)),
            rsrq=_safe_int(getattr(lte, "rsrq", None)),
            snr=_safe_int(getattr(lte, "snr", None)),
            isp_name=getattr(lte, "isp_name", None) or None,
            cpu_pct=_safe_float(getattr(status, "cpu_usage", None)),
            mem_pct=_safe_float(getattr(status, "mem_usage", None)),
        )

        return RouterSnapshot(
            total_bytes=int(lte.total_statistics) if lte.total_statistics is not None else None,
            rx_rate=int(lte.cur_rx_speed) if lte.cur_rx_speed is not None else None,
            tx_rate=int(lte.cur_tx_speed) if lte.cur_tx_speed is not None else None,
            wan_status=wan_status,
            clients=clients,
        )

    def _fetch_all(self):
        lte = self._lib.get_lte_status()
        status = self._lib.get_status()
        stat_rows = self._fetch_stat_rows()
        return lte, status, stat_rows

    def _fetch_stat_rows(self) -> dict[str, int]:
        """Map MAC → cumulative total_bytes, from DEV2_STAT_ENTRY."""
        acts = [self._lib.ActItem(self._lib.ActItem.GL, "DEV2_STAT_ENTRY")]
        _, values = self._lib.req_act(acts)
        if not values or not values[0]:
            return {}
        rows = values[0]
        result: dict[str, int] = {}
        for row in rows:
            mac = _normalise_mac(row["macAddress"])
            try:
                result[mac] = int(row["totalBytes"])
            except (KeyError, TypeError, ValueError):
                continue
        return result
