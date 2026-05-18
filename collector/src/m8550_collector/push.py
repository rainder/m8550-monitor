"""Web Push (VAPID) helpers — auto-managed key pair and dispatch.

The JSON file at ``vapid_path`` holds the public and private VAPID keys
(crypto material that must persist). The contact ``subject`` is runtime
config — read fresh from env on each start so it can be changed without
rotating keys.
"""
from __future__ import annotations

import json
import logging
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class VapidKeys:
    public: str            # URL-safe base64, what the browser uses
    private: str           # URL-safe base64 PEM-equivalent for py_vapid
    subject: str           # mailto:... or https://... contact URL


def load_or_create_vapid(vapid_path: str, subject: str) -> VapidKeys:
    """Read keys from ``vapid_path`` or generate a fresh pair and persist.

    ``subject`` always comes from the caller (env) so it can be changed
    later without rotating keys. A legacy ``subject`` key in the JSON is
    ignored. Legacy PEM-formatted private keys are migrated in place to
    raw base64 (which pywebpush's ``Vapid.from_string`` accepts directly).
    """
    p = Path(vapid_path)
    if p.exists():
        data = json.loads(p.read_text())
        priv_raw = _ensure_raw_private_key(data["private"])
        if priv_raw != data["private"]:
            log.info("migrating legacy PEM private key to raw base64 at %s", p)
            _atomic_write_keys(p, {"public": data["public"], "private": priv_raw})
        return VapidKeys(public=data["public"], private=priv_raw, subject=subject)
    keys = _generate_vapid_keys(subject)
    p.parent.mkdir(parents=True, exist_ok=True)
    _atomic_write_keys(p, {"public": keys.public, "private": keys.private})
    log.info("generated new VAPID key pair at %s", p)
    return keys


def _atomic_write_keys(p: Path, data: dict) -> None:
    fd, tmp = tempfile.mkstemp(dir=str(p.parent), prefix=".vapid.", suffix=".tmp")
    try:
        with os.fdopen(fd, "w") as f:
            json.dump(data, f)
        os.chmod(tmp, 0o600)
        os.replace(tmp, p)
    except Exception:
        try: os.unlink(tmp)
        except OSError: pass
        raise


def _ensure_raw_private_key(private: str) -> str:
    """Return the private key as URL-safe base64 of the 32-byte raw value.
    Accepts that exact form (passthrough) or PEM (one-time conversion)."""
    if not private.startswith("-----"):
        return private
    from cryptography.hazmat.primitives.serialization import load_pem_private_key
    from py_vapid.utils import b64urlencode
    key = load_pem_private_key(private.encode("ascii"), password=None)
    priv_int = key.private_numbers().private_value  # type: ignore[attr-defined]
    return b64urlencode(priv_int.to_bytes(32, byteorder="big"))


def _generate_vapid_keys(subject: str) -> VapidKeys:
    from cryptography.hazmat.primitives.asymmetric import ec
    from cryptography.hazmat.primitives import serialization
    from py_vapid.utils import b64urlencode

    priv = ec.generate_private_key(ec.SECP256R1())
    # Store as the raw 32-byte private value, url-safe base64 (no padding).
    # pywebpush's Vapid.from_string takes this form natively.
    priv_raw = priv.private_numbers().private_value.to_bytes(32, byteorder="big")
    # Web Push's "applicationServerKey" is the raw P-256 public key,
    # 65 bytes uncompressed, url-safe base64 with no padding.
    pub_bytes = priv.public_key().public_bytes(
        encoding=serialization.Encoding.X962,
        format=serialization.PublicFormat.UncompressedPoint,
    )
    return VapidKeys(public=b64urlencode(pub_bytes), private=b64urlencode(priv_raw), subject=subject)


@dataclass(frozen=True)
class PushSubscription:
    """Subset of a JS PushSubscription we need to send a push."""
    endpoint: str
    p256dh: str
    auth: str


def send_push(
    sub: PushSubscription,
    payload: dict,
    keys: VapidKeys,
) -> int:
    """Dispatch a single push. Returns the HTTP status from the push service.

    Caller should treat 404 / 410 as a permanently dead subscription and
    delete it from the store. Anything else is transient.
    """
    from pywebpush import webpush, WebPushException

    try:
        resp = webpush(
            subscription_info={
                "endpoint": sub.endpoint,
                "keys": {"p256dh": sub.p256dh, "auth": sub.auth},
            },
            data=json.dumps(payload),
            vapid_private_key=keys.private,
            vapid_claims={"sub": keys.subject},
            ttl=60 * 60 * 24,
        )
        return resp.status_code
    except WebPushException as e:
        if e.response is not None:
            return e.response.status_code
        raise


def dispatch_sms_pushes(
    new_messages,
    subscriptions: Iterable[PushSubscription],
    keys: VapidKeys,
) -> list[str]:
    """Send a push per new SMS to every subscription. Returns the list of
    endpoints that came back permanently dead (caller deletes them)."""
    dead: list[str] = []
    subs = list(subscriptions)
    if not subs or not new_messages:
        return dead
    for sub in subs:
        for msg in new_messages:
            payload = {
                "title": f"SMS · {msg.sender or 'Unknown'}",
                "body": _truncate(msg.content, 200),
                "tag": f"sms-{msg.id}",
                "data": {"id": msg.id, "receivedAt": msg.received_at},
            }
            try:
                status = send_push(sub, payload, keys)
            except Exception as e:
                log.warning("push to %s failed: %s", _redact(sub.endpoint), e)
                continue
            if status in (404, 410):
                dead.append(sub.endpoint)
                log.info("subscription expired: %s", _redact(sub.endpoint))
                break  # don't try further messages for a dead sub
    return dead


def _truncate(s: str, n: int) -> str:
    return s if len(s) <= n else s[: n - 1] + "…"


def _redact(endpoint: str) -> str:
    """Endpoint URLs identify a device; log only the host + a short hash tail."""
    from urllib.parse import urlparse
    p = urlparse(endpoint)
    tail = endpoint[-8:] if len(endpoint) > 8 else endpoint
    return f"{p.netloc}/…{tail}"
