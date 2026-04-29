"""Probe candidate 5G/NR signal OIDs and DEV2_LTE_NET_STATUS variants."""
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
    print(f"\n--- {label}: op={op} oid={oid} stack={stack} ---")
    item = router.ActItem(op, oid, stack, attrs=attrs) if attrs else router.ActItem(op, oid, stack)
    try:
        raw, values = router.req_act([item])
        print(f"raw: {raw[:600]}")
    except Exception as e:
        print(f"FAIL: {type(e).__name__}: {e}")


# 1) Try DEV2_LTE_NET_STATUS without attrs filter — maybe it returns more fields
probe("DEV2_LTE_NET_STATUS no-attrs", router.ActItem.GET, "DEV2_LTE_NET_STATUS")
# 2) Same with GS (get-statistics op)
probe("DEV2_LTE_NET_STATUS GS no-attrs", router.ActItem.GS, "DEV2_LTE_NET_STATUS")
# 3) GL operation
probe("DEV2_LTE_NET_STATUS GL no-attrs", router.ActItem.GL, "DEV2_LTE_NET_STATUS")

# Candidate 5G-specific OIDs
candidates = [
    ("DEV2_NR_NET_STATUS",      router.ActItem.GET),
    ("DEV2_5G_NET_STATUS",      router.ActItem.GET),
    ("DEV2_NR5G_NET_STATUS",    router.ActItem.GET),
    ("DEV2_LTE_NR_NET_STATUS",  router.ActItem.GET),
    ("DEV2_LTE_NR5G_NET_STATUS",router.ActItem.GET),
    ("DEV2_LTE_RAT_STATUS",     router.ActItem.GET),
    ("DEV2_RF_STATUS",          router.ActItem.GET),
    ("DEV2_SIGNAL_STATUS",      router.ActItem.GET),
    ("DEV2_RADIO_STATUS",       router.ActItem.GET),
    ("DEV2_LTE_CELL_STATUS",    router.ActItem.GET),
    ("DEV2_NR_CELL_STATUS",     router.ActItem.GET),
    ("DEV2_LTE_CARRIER_STATUS", router.ActItem.GET),
    ("DEV2_LTE_NET_INFO",       router.ActItem.GET),
    ("DEV2_LTE_INFO",           router.ActItem.GET),
    ("DEV2_LTE_LINK_CFG",       router.ActItem.GET),
    ("DEV2_LTE_LINK_STATUS",    router.ActItem.GET),
    ("DEV2_LTE_PHY",            router.ActItem.GET),
    ("DEV2_NR_PHY",             router.ActItem.GET),
    ("DEV2_LTE_NR_INFO",        router.ActItem.GET),
]
for oid, op in candidates:
    probe(f"GET {oid}", op, oid)
