import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Config:
    host: str
    password: str
    db_path: str
    poll_interval: int
    auth_backoff_seconds: int
    stale_session_threshold: int
    sms_poll_interval: int
    vapid_path: str
    vapid_subject: str


def load_config() -> Config:
    return Config(
        host=os.environ["M8550_HOST"],
        password=os.environ["M8550_PASSWORD"],
        db_path=os.environ["DB_PATH"],
        poll_interval=int(os.environ.get("POLL_INTERVAL", "5")),
        auth_backoff_seconds=int(os.environ.get("AUTH_BACKOFF_SECONDS", "300")),
        stale_session_threshold=int(os.environ.get("STALE_SESSION_THRESHOLD", "4")),
        sms_poll_interval=int(os.environ.get("SMS_POLL_INTERVAL", "60")),
        vapid_path=os.environ.get("VAPID_PATH", "/data/vapid.json"),
        vapid_subject=os.environ.get("VAPID_SUBJECT", "mailto:admin@example.com"),
    )
