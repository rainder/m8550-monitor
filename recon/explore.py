"""Deeper exploration: what fields actually have data on the M8550?"""
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

print(f"\n=== Client: {type(router).__name__}\n")

print("--- get_lte_status() ---")
try:
    lte = router.get_lte_status()
    print(json.dumps(lte.__dict__, indent=2, default=str))
except Exception as e:
    print(f"error: {e}")

print("\n--- get_ipv4_status() ---")
try:
    s = router.get_ipv4_status()
    print(json.dumps(s.__dict__, indent=2, default=str))
except Exception as e:
    print(f"error: {e}")

print("\n--- raw req_act on common stat endpoints ---")
# req_act is the library's low-level call. Let's see what endpoints exist.
import inspect
print(inspect.getsource(router.req_act))
