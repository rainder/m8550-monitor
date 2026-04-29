"""Hunt for the 5G-NR signal fields the local web UI shows.

The router web UI shows Signal Strength: 100%, SS-RSRP: -74 dBm,
SS-RSRQ: -10 dB, SS-SINR: 32 dB. So the data exists somewhere
locally — just under different attr names (SS = Synchronization
Signal, the 5G NR variant). Probe candidate attrs and OIDs.
"""
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
    print(f"\n--- {label} ---")
    item = router.ActItem(op, oid, stack, attrs=attrs) if attrs else router.ActItem(op, oid, stack)
    try:
        raw, values = router.req_act([item])
        print(f"raw: {raw[:1500]}")
    except Exception as e:
        print(f"FAIL: {type(e).__name__}: {e}")


# 1) Try existing OIDs with explicit SS-* attrs
ss_attrs = [
    "ssRsrp", "ssRsrq", "ssSinr", "ssRssi",
    "rfInfoSsRsrp", "rfInfoSsRsrq", "rfInfoSsSinr",
    "nrRsrp", "nrRsrq", "nrSinr", "nrRssi",
    "rsrp5g", "rsrq5g", "sinr5g",
    "signalStrength", "sigPercent", "sigStrength",
]
probe("DEV2_LTE_NET_STATUS with SS attrs", router.ActItem.GET, "DEV2_LTE_NET_STATUS", attrs=ss_attrs)
probe("DEV2_LTE_LINK_CFG with SS attrs",   router.ActItem.GET, "DEV2_LTE_LINK_CFG",   attrs=ss_attrs)

# 2) NR-specific OID candidates we missed
nr_oids = [
    "DEV2_LTE_NR_NET_STATUS_INFO",
    "DEV2_LTE_NETWORK_NR",
    "DEV2_LTE_NW_NR_STATUS",
    "DEV2_LTE_NR_INFO",
    "DEV2_LTE_NR_NETWORK_INFO",
    "DEV2_LTE_NR_LINK_CFG",
    "DEV2_LTE_NR_LINK_STATUS",
    "DEV2_LTE_PCC_STATUS",
    "DEV2_LTE_SCC_STATUS",
    "DEV2_LTE_CA_STATUS",
    "DEV2_LTE_EUTRAN_STATUS",
    "DEV2_LTE_MCG_STATUS",
    "DEV2_LTE_SCG_STATUS",
    "DEV2_LTE_5G_INFO",
    "DEV2_5G_INFO",
    "DEV2_NR_INFO",
    "DEV2_NR5G_INFO",
    "DEV2_NR5G_NET_STATUS",
    "DEV2_LTE_NR5G_NET_STATUS",
    "DEV2_LTE_NR_RF_STATUS",
    "DEV2_LTE_RF_STATUS",
    "DEV2_LTE_INFO",
    "DEV2_LTE_LINK_INFO",
    "DEV2_LTE_INET_INFO",
    "DEV2_LTE_INTERNET_INFO",
    "DEV2_LTE_DASHBOARD",
    "DEV2_LTE_BASIC",
    "DEV2_LTE_NM",
    "DEV2_LTE_OBSERVER",
    "DEV2_LTE_WANSTATUS",
]
for oid in nr_oids:
    probe(f"GET {oid}", router.ActItem.GET, oid)
