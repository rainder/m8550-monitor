import time
from dataclasses import dataclass
from typing import Callable, Protocol

import requests


@dataclass(frozen=True)
class RouterClientSnapshot:
    """One reading for a single connected device."""
    mac: str
    name: str | None
    ip: str | None
    conn_type: str             # "host_2g" | "host_5g" | "wired"
    total_bytes: int | None    # cumulative combined RX+TX from DEV2_STAT_ENTRY; None if no stat row
    # Cumulative packets (sent+received) from the AP-association layer
    # (DEV2_ADT_WIFI_CLIENT). DEV2_STAT_ENTRY.totalBytes only tracks
    # connection-tracking metadata on M8550 firmware (under-counts real
    # throughput by ~1000×), so packet deltas scaled by an avg packet size
    # derived from the WAN counter are our actual per-client bandwidth
    # signal. None for wired clients or when the AP-stats fetch fails.
    packets_total: int | None = None


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
    sms_unread_count: int | None = None


@dataclass(frozen=True)
class SmsMessage:
    """One SMS in the router's inbox."""
    id: int                  # router-side index field; stable across polls
    sender: str
    content: str
    received_at: int         # unix seconds (UTC)
    unread: bool


class RouterClient(Protocol):
    def snapshot(self) -> RouterSnapshot:
        """Authenticate if needed and return one reading.

        Raises ConnectionError on unreachable, AuthError on bad credentials.
        """
        ...

    def list_sms(self) -> list[SmsMessage]:
        """Return the router's SMS inbox. May raise the same exceptions as snapshot()."""
        ...

    def mark_sms_read(self, message_id: int) -> bool:
        """Mark the SMS with the given router-side index as read.

        Returns True on success, False if the message is no longer on the router.
        May raise the same exceptions as snapshot().
        """
        ...

    def force_reauth(self) -> bool:
        """Clear any active backoff and immediately try to reclaim the router
        session. User-triggered: only call when the user explicitly asks for
        it (e.g. they closed Tether and don't want to wait out the 60s).

        Returns True on successful reauth. On failure the backoff is re-armed
        and the method may raise AuthError or ConnectionError.
        """
        ...


class AuthError(Exception):
    """Session is unusable due to contention (likely the Tether app)."""
    def __init__(self, message: str, retry_after: int = 0):
        super().__init__(message)
        self.retry_after = retry_after


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


def _router_busy(host: str, timeout: float = 5.0) -> bool:
    """Ask the router whether another session holds the auth slot. Hits
    /cgi/getBusy unauthenticated — the official web UI uses the same probe
    to decide whether to show its "kick existing session?" popup.

    Response semantics (observed on M8550 firmware):
      - HTTP 200 with body containing ``isBusy=1`` → someone else is logged in
      - HTTP 200 with body containing ``isBusy=0`` → nobody is logged in
      - HTTP 406 → we already own the session (probe sent our own JSESSIONID)
      - anything else (network error, parse failure) → fail open and return
        False; better to attempt the login than freeze the collector based
        on an unreliable signal.
    """
    try:
        r = requests.post(
            f"{host.rstrip('/')}/cgi/getBusy",
            headers={"Referer": host, "Origin": host},
            timeout=timeout,
        )
    except Exception as e:
        log.debug("getBusy probe failed (%s); assuming not busy", e)
        return False
    if r.status_code != 200:
        return False
    return "isBusy=1" in r.text


def _parse_received_time(s) -> int | None:
    """Router returns local-tz strings like "2026-02-20 16:01:19". Treat as UTC
    since the router clock is its own beast; the consumer can format with
    its own offset if needed. Returns None on parse failure."""
    if not s:
        return None
    from datetime import datetime, timezone
    try:
        dt = datetime.strptime(str(s), "%Y-%m-%d %H:%M:%S")
        return int(dt.replace(tzinfo=timezone.utc).timestamp())
    except (TypeError, ValueError):
        return None


class LibRouterClient:
    """Adapter from tplinkrouterc6u (M8550 / TPLinkEXClient) to RouterClient.

    The M8550 allows exactly one logged-in session at a time. When the Tether
    app logs in it invalidates ours, and re-authorising immediately would
    just kick Tether back — a tug-of-war. Instead, when a fetch fails for a
    non-network reason we treat the slot as contested and back off for
    ``auth_backoff_seconds`` (default 5 minutes) before trying to reclaim it.
    """

    def __init__(
        self,
        host: str = "",
        password: str = "",
        _lib=None,
        *,
        auth_backoff_seconds: int = 300,
        stale_session_threshold: int = 4,
        busy_probe: Callable[[], bool] | None = None,
        _now: Callable[[], int] = lambda: int(time.time()),
    ):
        self._auth_backoff_seconds = auth_backoff_seconds
        self._stale_session_threshold = stale_session_threshold
        self._now = _now
        self._kicked_until: int | None = None
        self._consecutive_oserrors = 0
        # busy_probe returns True when another session is active. Defaults to
        # hitting /cgi/getBusy on the configured host. Tests override it.
        if busy_probe is not None:
            self._busy_probe = busy_probe
        elif host:
            self._busy_probe = lambda: _router_busy(host)
        else:
            self._busy_probe = lambda: False  # no host → no remote probe
        if _lib is not None:
            self._lib = _lib
            return
        from tplinkrouterc6u import TplinkRouterProvider
        self._lib = TplinkRouterProvider.get_client(
            host, password, username="user", logger=log,
        )
        try:
            self._safe_authorize()
        except AuthError as e:
            # Don't fail container startup if Tether already holds the session
            # — _kicked_until is armed; snapshot() will retry after backoff.
            log.warning("startup: %s", e)

    def _safe_authorize(self) -> None:
        """authorize() unless another session is active. If busy, arm the
        kick cooldown and raise AuthError instead of stealing the session."""
        if self._busy_probe():
            now = self._now()
            self._kicked_until = now + self._auth_backoff_seconds
            raise AuthError(
                f"another session is active; backing off "
                f"{self._auth_backoff_seconds}s to avoid kicking it",
                retry_after=self._auth_backoff_seconds,
            )
        self._lib.authorize()

    def snapshot(self) -> RouterSnapshot:
        now = self._now()
        if self._kicked_until is not None:
            if now < self._kicked_until:
                remaining = self._kicked_until - now
                raise AuthError(
                    f"session contention backoff ({remaining}s remaining)",
                    retry_after=remaining,
                )
            self._kicked_until = None
            try:
                self._safe_authorize()
            except AuthError:
                # _safe_authorize armed the cooldown when it detected a busy
                # router — propagate as-is.
                raise
            except Exception as e:
                self._kicked_until = now + self._auth_backoff_seconds
                raise AuthError(
                    f"reauth after backoff failed: {e}",
                    retry_after=self._auth_backoff_seconds,
                ) from e

        try:
            lte, status, stat_rows = self._fetch_all()
        except OSError as e:
            # The M8550 doesn't always 401 a kicked session — sometimes it just
            # resets the connection (RemoteDisconnected). Those look like
            # network errors. Tolerate a few in a row as genuine transient
            # blips; once the count hits the threshold the session is most
            # likely stale and worth one reauth attempt.
            self._consecutive_oserrors += 1
            if self._consecutive_oserrors < self._stale_session_threshold:
                raise ConnectionError(str(e)) from e
            try:
                self._safe_authorize()
                lte, status, stat_rows = self._fetch_all()
            except AuthError:
                self._consecutive_oserrors = 0
                raise
            except Exception as reauth_err:
                self._kicked_until = now + self._auth_backoff_seconds
                self._consecutive_oserrors = 0
                raise AuthError(
                    f"session reauth after {self._stale_session_threshold} "
                    f"connection errors failed: {reauth_err}",
                    retry_after=self._auth_backoff_seconds,
                ) from reauth_err
            self._consecutive_oserrors = 0
        except Exception as e:
            self._kicked_until = now + self._auth_backoff_seconds
            self._consecutive_oserrors = 0
            raise AuthError(
                f"session lost (likely Tether contention); backing off "
                f"{self._auth_backoff_seconds}s: {e}",
                retry_after=self._auth_backoff_seconds,
            ) from e
        else:
            self._consecutive_oserrors = 0

        wifi_packets = self._fetch_wifi_client_packets()
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
                    packets_total=wifi_packets.get(mac),
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
            sms_unread_count=_safe_int(getattr(lte, "sms_unread_count", None)),
        )

    def list_sms(self) -> list["SmsMessage"]:
        """Fetch the inbox. M8550 paginates at 8 messages/page; iterate until
        the router returns an empty page.

        The PageNumber attr is passed as a pre-quoted JSON fragment because
        tplinkrouterc6u's EX-firmware serializer only quotes attrs that lack
        ``:`` — passing ``"PageNumber=1"`` would be mangled into the malformed
        key ``"PageNumber=1":""`` and the SET would silently fail (errorcode
        9007), leaving the GL on whatever page the router happens to be on.
        """
        out: list[SmsMessage] = []
        seen_ids: set[int] = set()
        for page in range(1, 21):  # 20 pages × 8 = 160 msgs, far above any real inbox
            acts = [
                self._lib.ActItem(
                    self._lib.ActItem.SET, "DEV2_LTE_SMS_RECVMSGBOX",
                    attrs=[f'"PageNumber":"{page}"'],
                ),
                self._lib.ActItem(
                    self._lib.ActItem.GL, "DEV2_LTE_SMS_RECVMSGENTRY",
                    attrs=["index", "from", "content", "receivedTime", "unread"],
                ),
            ]
            try:
                _, values = self._lib.req_act(acts)
            except OSError as e:
                raise ConnectionError(str(e)) from e
            if not values or not values[0]:
                break
            rows = values[0]
            added = 0
            for row in rows:
                if not isinstance(row, dict):
                    continue
                idx = _safe_int(row.get("index"))
                if idx is None or idx in seen_ids:
                    continue
                received_at = _parse_received_time(row.get("receivedTime"))
                if received_at is None:
                    continue
                seen_ids.add(idx)
                out.append(SmsMessage(
                    id=idx,
                    sender=str(row.get("from") or ""),
                    content=str(row.get("content") or ""),
                    received_at=received_at,
                    unread=str(row.get("unread") or "0") == "1",
                ))
                added += 1
            if added == 0:
                # Either the page was truly empty or the router ignored
                # PageNumber and returned a page we've already absorbed.
                break
        return out

    def _locate_sms(self, message_id: int) -> tuple[int, int] | None:
        """Walk pages until we find the (page, slot) holding ``message_id``.

        ``slot`` is the 1-based row position within the page — it shifts when
        other rows are deleted, so callers must re-locate before each mutation.
        """
        for page in range(1, 21):
            try:
                _, values = self._lib.req_act([
                    self._lib.ActItem(
                        self._lib.ActItem.SET, "DEV2_LTE_SMS_RECVMSGBOX",
                        attrs=[f'"PageNumber":"{page}"'],
                    ),
                    self._lib.ActItem(
                        self._lib.ActItem.GL, "DEV2_LTE_SMS_RECVMSGENTRY",
                        attrs=["index"],
                    ),
                ])
            except OSError as e:
                raise ConnectionError(str(e)) from e
            if not values or not values[0]:
                return None
            rows = values[0]
            if not isinstance(rows, list):
                return None
            for slot, row in enumerate(rows, start=1):
                if isinstance(row, dict) and _safe_int(row.get("index")) == message_id:
                    return page, slot
        return None

    def mark_sms_read(self, message_id: int) -> bool:
        located = self._locate_sms(message_id)
        if located is None:
            return False
        page, slot = located
        try:
            self._lib.req_act([
                self._lib.ActItem(
                    self._lib.ActItem.SET, "DEV2_LTE_SMS_RECVMSGBOX",
                    attrs=[f'"PageNumber":"{page}"'],
                ),
                self._lib.ActItem(
                    self._lib.ActItem.SET, "DEV2_LTE_SMS_RECVMSGENTRY",
                    f"{slot},0,0,0,0,0", attrs=['"unread":"0"'],
                ),
            ])
        except OSError as e:
            raise ConnectionError(str(e)) from e
        return True

    # No router-side delete: the M8550 EX firmware rejects `del` on
    # DEV2_LTE_SMS_RECVMSGENTRY (errorcode 71011) and there's no settable attr
    # we found that removes a message. The poller handles "delete" actions as
    # a local soft-hide instead — see Store.hide_sms_local().

    def force_reauth(self) -> bool:
        """Bypass the auth backoff and try to reclaim the session immediately."""
        self._kicked_until = None
        self._consecutive_oserrors = 0
        try:
            self._lib.authorize()
        except Exception as e:
            self._kicked_until = self._now() + self._auth_backoff_seconds
            raise AuthError(
                f"force reauth failed: {e}",
                retry_after=self._auth_backoff_seconds,
            ) from e
        return True

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

    def _fetch_wifi_client_packets(self) -> dict[str, int]:
        """Map MAC → cumulative packets (sent+received), from DEV2_ADT_WIFI_CLIENT.

        This is the only per-client counter on M8550 firmware that tracks real
        throughput. DEV2_STAT_ENTRY.totalBytes turned out to count only
        connection-tracking metadata; bulk transfer bypasses it entirely.
        """
        try:
            _, values = self._lib.req_act([
                self._lib.ActItem(
                    self._lib.ActItem.GL, "DEV2_ADT_WIFI_CLIENT",
                    attrs=["MACAddress", "packetsSent", "packetsReceived"],
                )
            ])
        except Exception:
            return {}
        if not values or not values[0]:
            return {}
        result: dict[str, int] = {}
        for row in values[0]:
            if not isinstance(row, dict):
                continue
            mac = row.get("MACAddress")
            if not mac:
                continue
            try:
                ps = int(row.get("packetsSent") or 0)
                pr = int(row.get("packetsReceived") or 0)
            except (TypeError, ValueError):
                continue
            result[_normalise_mac(str(mac))] = ps + pr
        return result
