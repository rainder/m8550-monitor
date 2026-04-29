"""Sustain a session and poll DEV2_LTE_NET_STATUS for 30s — does anything ever
budge from zero?"""
import os
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

INTERESTING = ("sigLevel", "rfInfoRssi", "rfInfoRsrp", "rfInfoRsrq", "rfInfoSnr",
               "rfInfoEcio", "rfInfoChannel", "rfInfoBand", "rfInfoIf", "rfInfoRat",
               "signalStrength")

seen = {k: set() for k in INTERESTING}

start = time.time()
ticks = 0
while time.time() - start < 30:
    ticks += 1
    try:
        items = [
            router.ActItem(router.ActItem.GET, "DEV2_LTE_NET_STATUS", "1,0,0,0,0,0"),
            router.ActItem(router.ActItem.GET, "DEV2_LTE_LINK_CFG",   "1,0,0,0,0,0"),
        ]
        _, values = router.req_act(items)
        net = values[0] if isinstance(values[0], dict) else (values[0][0] if values[0] else {})
        link = values[1] if isinstance(values[1], dict) else (values[1][0] if values[1] else {})
        snapshot = {**net, **link}
        for k in INTERESTING:
            if k in snapshot:
                seen[k].add(snapshot[k])
    except Exception as e:
        print(f"tick {ticks}: {type(e).__name__}: {e}")
        try:
            router.authorize()
        except Exception:
            pass
    time.sleep(1)

print(f"\n--- after {ticks} ticks ({time.time()-start:.1f}s) ---")
for k, vals in seen.items():
    print(f"  {k:18s}  values seen: {sorted(vals)}")
