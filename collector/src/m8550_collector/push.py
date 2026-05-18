"""Web Push (VAPID) helpers — auto-managed key pair and dispatch.

A single JSON file at ``vapid_path`` holds both the public and private
VAPID keys plus the contact subject. The collector generates the file
on first run and the web service reads the public key from it; bind-
mounting ``/data`` into both containers lets them share without an env
var ceremony.
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
    """Read keys from ``vapid_path`` or generate a fresh pair and persist."""
    p = Path(vapid_path)
    if p.exists():
        data = json.loads(p.read_text())
        return VapidKeys(
            public=data["public"], private=data["private"],
            subject=data.get("subject", subject),
        )
    keys = _generate_vapid_keys(subject)
    p.parent.mkdir(parents=True, exist_ok=True)
    # Atomic write so we never half-write a key file.
    fd, tmp = tempfile.mkstemp(dir=str(p.parent), prefix=".vapid.", suffix=".tmp")
    try:
        with os.fdopen(fd, "w") as f:
            json.dump(
                {"public": keys.public, "private": keys.private, "subject": keys.subject},
                f,
            )
        os.chmod(tmp, 0o600)
        os.replace(tmp, p)
    except Exception:
        try: os.unlink(tmp)
        except OSError: pass
        raise
    log.info("generated new VAPID key pair at %s", p)
    return keys


def _generate_vapid_keys(subject: str) -> VapidKeys:
    from cryptography.hazmat.primitives.asymmetric import ec
    from cryptography.hazmat.primitives import serialization
    from py_vapid.utils import b64urlencode

    priv = ec.generate_private_key(ec.SECP256R1())
    priv_pem = priv.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode("ascii")
    # Web Push's "applicationServerKey" is the raw P-256 public key,
    # 65 bytes uncompressed, url-safe base64 with no padding.
    pub_bytes = priv.public_key().public_bytes(
        encoding=serialization.Encoding.X962,
        format=serialization.PublicFormat.UncompressedPoint,
    )
    return VapidKeys(public=b64urlencode(pub_bytes), private=priv_pem, subject=subject)


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
