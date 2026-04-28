import os
import json
from logging import Logger, INFO, basicConfig

basicConfig(level=INFO)
logger = Logger("recon")

from tplinkrouterc6u import TplinkRouterProvider

password = os.environ["M8550_PASSWORD"]
try:
    router = TplinkRouterProvider.get_client(
        "http://192.168.1.1",
        password,
        username="user",
        logger=logger,
    )
    router.authorize()
    print(f"=== Picked client: {type(router).__name__} (username=user)")
except Exception as e:
    print(f"username=user failed: {e}")
    router = TplinkRouterProvider.get_client(
        "http://192.168.1.1",
        password,
        username="admin",
        logger=logger,
    )
    router.authorize()
    print(f"=== Picked client: {type(router).__name__} (username=admin)")

status = router.get_status()
print("=== STATUS ===")
print(json.dumps(status.__dict__, indent=2, default=str))

print("=== DEVICES ===")
for d in getattr(status, "devices", []):
    print(json.dumps(d.__dict__, indent=2, default=str))
