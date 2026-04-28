"""Try GS / GO operations on DEV2_STAT_ENTRY, sample currBytes twice for delta sanity."""
import os
import json
import time
from logging import Logger, INFO, basicConfig

basicConfig(level=INFO)
logger = Logger("recon")

from tplinkrouterc6u import TplinkRouterProvider

password = os.environ["M8550_PASSWORD"]
router = TplinkRouterProvider.get_client(
    "http://192.168.1.1", password, username="user", logger=logger
)
router.authorize()


def probe(label, op, oid, attrs=None):
    print(f"\n--- {label}: op={op} oid={oid} ---")
    item = router.ActItem(op, oid)
    if attrs:
        item = router.ActItem(op, oid, attrs=attrs)
    try:
        raw, values = router.req_act([item])
        print(f"raw: {raw[:600]}")
    except Exception as e:
        print(f"FAIL: {type(e).__name__}: {e}")


probe("GS DEV2_STAT_ENTRY", router.ActItem.GS, "DEV2_STAT_ENTRY")
probe("GO DEV2_STAT_ENTRY", router.ActItem.GO, "DEV2_STAT_ENTRY")

print("\n=== Sample DEV2_STAT_ENTRY twice, 5s apart ===")
for i in range(2):
    item = router.ActItem(router.ActItem.GL, "DEV2_STAT_ENTRY")
    raw, values = router.req_act([item])
    print(f"\nsample {i+1}:")
    for entry in values[0]:
        if entry.get("macAddress") in ("AA:BB:CC:DD:EE:02", "AA:BB:CC:DD:EE:05"):
            print(f"  {entry.get('macAddress')}: totalBytes={entry.get('totalBytes')} currBytes={entry.get('currBytes')} totalPkts={entry.get('totalPkts')} currPkts={entry.get('currPkts')}")
    if i == 0:
        time.sleep(5)
