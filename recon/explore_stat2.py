"""Probe more candidate oids for direction-split per-host traffic."""
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
        print(f"raw: {raw[:600]}")
    except Exception as e:
        print(f"FAIL: {type(e).__name__}: {e}")


# DEV2_STAT_ENTRY with explicit attribute filter for direction-split fields.
DIR_ATTRS = [
    "ipAddress", "macAddress",
    "totalBytes", "currBytes", "totalPkts", "currPkts",
    "totalBytesRx", "totalBytesTx", "currBytesRx", "currBytesTx",
    "totalRxBytes", "totalTxBytes", "currRxBytes", "currTxBytes",
    "rxBytes", "txBytes",
    "downBytes", "upBytes",
    "downSpeed", "upSpeed",
    "downRate", "upRate",
    "rxRate", "txRate",
    "X_TP_TotalBytesSent", "X_TP_TotalBytesReceived",
    "X_TP_CurrBytesSent", "X_TP_CurrBytesReceived",
]
probe("DEV2_STAT_ENTRY with direction-split attrs",
      [router.ActItem(router.ActItem.GL, "DEV2_STAT_ENTRY", attrs=DIR_ATTRS)])

# More candidate oids.
candidates = [
    "DEV2_RATE_ENTRY",
    "DEV2_TRAFFIC_ENTRY",
    "DEV2_BANDWIDTH_ENTRY",
    "DEV2_HOST_RATE",
    "DEV2_HOST_BANDWIDTH",
    "DEV2_HOST_THROUGHPUT",
    "DEV2_TRAFFIC_HOST",
    "DEV2_TRAFFIC_RATE",
    "DEV2_TRAFFIC_DOWNUP",
    "DEV2_HOST_TRAFFIC_ENTRY",
    "DEV2_PER_HOST_TRAFFIC",
]
for oid in candidates:
    probe(f"GL {oid}", [router.ActItem(router.ActItem.GL, oid)])
