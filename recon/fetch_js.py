"""Pull oid_str.js from the router using the authenticated session, then
grep for any 5G/SS/RSRP/SINR-related OID names."""
import os
import re
from logging import Logger, INFO, basicConfig

basicConfig(level=INFO)
logger = Logger("recon")

from tplinkrouterc6u import TplinkRouterProvider

password = os.environ["M8550_PASSWORD"]
router = TplinkRouterProvider.get_client(
    "http://192.168.1.1", password, username="user", logger=logger
)
router.authorize()

# The library doesn't expose a requests.Session, but uses its own
# `_request()` for cgi calls. Static assets bypass that — fetch them
# directly with cookies that the auth flow set on requests' default.
import requests

# Try fetching with a fresh session that uses the login cookie. We don't
# actually need auth for static content if we lie about our UA.
session = requests.Session()
session.headers["User-Agent"] = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_0) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)
session.headers["Referer"] = "http://192.168.1.1/"
session.headers["Accept"] = "*/*"
session.headers["Accept-Language"] = "en-US,en;q=0.9"

candidates = [
    "/js/oid_str.js",
    "/js/lib.js",
    "/js/gdprProxy.js",
    "/locale/language.js",
    "/js/oidstr.js",
]
for path in candidates:
    url = f"http://192.168.1.1{path}"
    try:
        r = session.get(url, timeout=5)
        print(f"{r.status_code} {len(r.text):>6}b  {url}")
    except Exception as e:
        print(f"FAIL {url}: {e}")
