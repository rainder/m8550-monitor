"""Aggressive probe for live signal data: different stacks, more OIDs, refresh."""
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


def probe(label, op, oid, stack="1,0,0,0,0,0", attrs=None):
    print(f"\n--- {label} ({op} {oid} stack={stack}) ---")
    item = router.ActItem(op, oid, stack, attrs=attrs) if attrs else router.ActItem(op, oid, stack)
    try:
        raw, values = router.req_act([item])
        print(f"raw: {raw[:600]}")
        return values
    except Exception as e:
        print(f"FAIL: {type(e).__name__}: {e}")
        return None


# 1) DEV2_LTE_NET_STATUS at every stack from 0..5
for s in range(6):
    probe(f"NET_STATUS stack={s}", router.ActItem.GET, "DEV2_LTE_NET_STATUS", stack=f"{s},0,0,0,0,0")

# 2) DEV2_LTE_LINK_CFG with all attrs (full dump) at multiple stacks
for s in range(3):
    probe(f"LINK_CFG stack={s}", router.ActItem.GET, "DEV2_LTE_LINK_CFG", stack=f"{s},0,0,0,0,0")

# 3) New candidate OIDs
for oid in [
    "DEV2_LTE_RF_INFO",
    "DEV2_LTE_RF",
    "DEV2_RF_INFO",
    "DEV2_LTE_NW_STATUS",
    "DEV2_NW_STATUS",
    "DEV2_LTE_DIAG",
    "DEV2_LTE_SIGNAL_INFO",
    "DEV2_LTE_NET_STATUS_EXT",
    "DEV2_LTE_NET_STATUS2",
    "DEV2_LTE_5G_NET_STATUS",
    "DEV2_LTE_NR_RF_INFO",
    "DEV2_NR_RF_INFO",
    "DEV2_LTE_PHY_STATUS",
    "DEV2_LTE_INTF_STATUS",
    "DEV2_LTE_INTF_INFO",
    "DEV2_XTP_LTE_INTF_CFG",   # known to work for traffic
    "DEV2_XTP_LTE_INTF_STATUS",
    "DEV2_XTP_LTE_RF",
]:
    probe(f"GET {oid}", router.ActItem.GET, oid)
    probe(f"GL {oid}",  router.ActItem.GL,  oid)

# 4) Try a "set to refresh" pattern — some firmwares have a refresh trigger
print("\n=== trying SO/refresh patterns ===")
for oid in ["DEV2_LTE_REFRESH", "DEV2_LTE_RF_REFRESH", "DEV2_LTE_DIAG_RUN", "DEV2_LTE_SCAN"]:
    probe(f"SET {oid}", router.ActItem.SET, oid)
