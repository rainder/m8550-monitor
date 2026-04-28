"""Probe candidate oids/attrs for per-client traffic on M8550."""
import os
import json
from logging import Logger, INFO, basicConfig

basicConfig(level=INFO)
logger = Logger("recon")

from tplinkrouterc6u import TplinkRouterProvider

password = os.environ["M8550_PASSWORD"]
router = TplinkRouterProvider.get_client(
    "http://192.168.1.1", password, username="user", logger=logger
)
router.authorize()


def probe(label, items):
    print(f"\n--- {label} ---")
    try:
        raw, values = router.req_act(items)
        print(f"raw: {raw[:300]}")
        print(f"values: {json.dumps(values, indent=2, default=str)[:1200]}")
    except Exception as e:
        print(f"FAIL: {type(e).__name__}: {e}")


# Common attribute names for traffic on TR-181 / TP-Link's TR-098-flavoured oids.
TRAFFIC_ATTRS = [
    "active",
    "X_TP_LanConnType",
    "physAddress",
    "IPAddress",
    "hostName",
    "X_TP_TotalPacketsSent",
    "X_TP_TotalPacketsReceived",
    "X_TP_TotalBytesSent",
    "X_TP_TotalBytesReceived",
    "X_TP_CurrentBytesSent",
    "X_TP_CurrentBytesReceived",
    "X_TP_DownloadRate",
    "X_TP_UploadRate",
    "X_TP_DownSpeed",
    "X_TP_UpSpeed",
    "currBytesRx",
    "currBytesTx",
    "totalBytesRx",
    "totalBytesTx",
    "downSpeed",
    "upSpeed",
]

# Try the existing host entry but with extra attrs.
probe(
    "DEV2_HOST_ENTRY with expanded attrs",
    [router.ActItem(router.ActItem.GL, "DEV2_HOST_ENTRY", attrs=TRAFFIC_ATTRS)],
)

# Try other plausible oids related to clients and traffic.
candidates = [
    "DEV2_HOST_TRAFFIC",
    "DEV2_HOSTS_TRAFFIC",
    "DEV2_TRAFFIC_STATS",
    "DEV2_LANHOST_STAT",
    "DEV2_LAN_HOST_STAT",
    "DEV2_LAN_TRAFFIC",
    "DEV2_WAN_TRAFFIC",
    "DEV2_STAT_ENTRY",
    "DEV2_STAT_HOSTS",
    "DEV2_STAT",
    "DEV2_HOST_STAT",
    "DEV2_TRAFFIC",
    "TRAFFIC_STAT",
    "STAT",
]
for oid in candidates:
    probe(f"GL {oid}", [router.ActItem(router.ActItem.GL, oid)])
