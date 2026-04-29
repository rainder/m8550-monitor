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
    """Signal, ISP, link, and system-resource fields from the router.

    Real RF metrics come from DEV2_LTE_SERVING_CELL_INFO (OID gl). The
    older DEV2_LTE_NET_STATUS always returns 0 for rfInfoRsrp etc on
    M8550 firmware.
    """
    sig_level: int | None
    rsrp: int | None             # LTE serving-cell RSRP (real value when on LTE)
    rsrq: int | None             # LTE serving-cell RSRQ
    snr: int | None              # LTE serving-cell SNR (×10; 60 = 6.0 dB)
    isp_name: str | None
    cpu_pct: float | None
    mem_pct: float | None
    connected_band: str | None       # e.g. "B3;N40" (LTE B3 + NR N40)
    endc_status: int | None          # 1 = EN-DC active (5G NSA), 0 = LTE only
    network_type: int | None         # firmware-specific code (8 = 5G NSA on M8550)
    wan_ipv4: str | None
    wan_ipv6: str | None
    # 5G NR primary cell (SS- = Synchronization Signal)
    ss_rsrp: int | None          # 5G NR SS-RSRP dBm
    ss_rsrq: int | None          # 5G NR SS-RSRQ dB
    ss_sinr: int | None          # 5G NR SS-SINR ×10 (310 = 31.0 dB)
    nr_signal_strength: int | None   # 0..5
    nr_band: str | None          # e.g. "40"
    # LTE primary cell extras
    lte_signal_strength: int | None  # 0..5
    lte_band: str | None         # e.g. "3"


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

        link_cfg = self._fetch_link_cfg()
        lte_cell, nr_cell = self._fetch_serving_cells()
        wan_status = WanStatus(
            sig_level=_safe_int(getattr(lte, "sig_level", None)),
            rsrp=_safe_int(lte_cell.get("RSRP")),
            rsrq=_safe_int(lte_cell.get("RSRQ")),
            snr=_safe_int(lte_cell.get("SNR")),
            isp_name=getattr(lte, "isp_name", None) or None,
            cpu_pct=_safe_float(getattr(status, "cpu_usage", None)),
            mem_pct=_safe_float(getattr(status, "mem_usage", None)),
            connected_band=link_cfg.get("connectedBand") or None,
            endc_status=_safe_int(link_cfg.get("endcStatus")),
            network_type=_safe_int(link_cfg.get("networkType")),
            wan_ipv4=link_cfg.get("ipv4") or None,
            wan_ipv6=link_cfg.get("ipv6") or None,
            ss_rsrp=_safe_int(nr_cell.get("SSRSRP")),
            ss_rsrq=_safe_int(nr_cell.get("SSRSRQ")),
            ss_sinr=_safe_int(nr_cell.get("SSSINR")),
            nr_signal_strength=_safe_int(nr_cell.get("signalStrength")),
            nr_band=(nr_cell.get("band") or None),
            lte_signal_strength=_safe_int(lte_cell.get("signalStrength")),
            lte_band=(lte_cell.get("band") or None),
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

    def _fetch_link_cfg(self) -> dict:
        """DEV2_LTE_LINK_CFG carries the band / EN-DC / WAN IP info the
        higher-level get_lte_status() call drops."""
        acts = [self._lib.ActItem(
            self._lib.ActItem.GET, "DEV2_LTE_LINK_CFG", "1,0,0,0,0,0",
        )]
        try:
            _, values = self._lib.req_act(acts)
        except Exception:
            return {}
        if not values:
            return {}
        v = values[0]
        # The CGI returns either a dict (single entry) or [dict] (list of one).
        if isinstance(v, list):
            v = v[0] if v else {}
        return v if isinstance(v, dict) else {}

    def _fetch_serving_cells(self) -> tuple[dict, dict]:
        """Returns (lte_cell, nr_cell). Either may be empty {} when not connected.

        Active cells are those with cellConnectionStatus == "1". The router
        returns up to one LTE entry (networkType "3") and one NR entry
        (networkType "8") on this M8550 firmware.
        """
        try:
            acts = [self._lib.ActItem(self._lib.ActItem.GL, "DEV2_LTE_SERVING_CELL_INFO")]
            _, values = self._lib.req_act(acts)
        except Exception:
            return {}, {}
        if not values or not values[0]:
            return {}, {}
        lte_cell, nr_cell = {}, {}
        for entry in values[0]:
            if not isinstance(entry, dict):
                continue
            if str(entry.get("cellConnectionStatus")) != "1":
                continue
            nt = str(entry.get("networkType"))
            if nt == "3":
                lte_cell = entry
            elif nt == "8":
                nr_cell = entry
        return lte_cell, nr_cell

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
