"""Probe STAT_ENTRY (per-client traffic) using the EX-client session."""
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
print(f"Client: {type(router).__name__}\n")

# Use the same low-level ACT mechanism as the MR client.
acts = [router.ActItem(router.ActItem.GL, "STAT_ENTRY")]
try:
    raw, values = router.req_act(acts)
    print("=== raw response ===")
    print(raw[:2000])
    print("\n=== parsed values ===")
    print(json.dumps(values, indent=2, default=str))
except Exception as e:
    print(f"STAT_ENTRY failed: {type(e).__name__}: {e}")
