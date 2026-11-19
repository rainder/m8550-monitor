import logging
import signal
import sys

from .config import load_config
from .poller import Poller
from .push import load_or_create_vapid
from .router import LibRouterClient
from .store import Store


def main() -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    log = logging.getLogger("m8550-collector")

    cfg = load_config()
    log.info(
        "starting collector host=%s db=%s interval=%ds auth_backoff=%ds "
        "stale_session_threshold=%d",
        cfg.host, cfg.db_path, cfg.poll_interval, cfg.auth_backoff_seconds,
        cfg.stale_session_threshold,
    )

    store = Store(cfg.db_path)
    store.init_schema()
    vapid = load_or_create_vapid(cfg.vapid_path, cfg.vapid_subject)
    log.info("vapid public key: %s…", vapid.public[:24])
    router = LibRouterClient(
        host=cfg.host,
        password=cfg.password,
        auth_backoff_seconds=cfg.auth_backoff_seconds,
        stale_session_threshold=cfg.stale_session_threshold,
    )
    # PID 1 in the container: without a handler Python ignores SIGTERM, Docker
    # SIGKILLs us after the grace period, and our router session is orphaned
    # (locking the next collector out for ~10 min). Turn it into SystemExit so
    # the finally block logs out cleanly.
    def _on_sigterm(signum, frame):
        raise SystemExit(0)
    signal.signal(signal.SIGTERM, _on_sigterm)

    try:
        Poller(
            router, store,
            sms_poll_interval=cfg.sms_poll_interval,
            vapid_keys=vapid,
        ).run_forever(cfg.poll_interval)
    finally:
        log.info("shutting down; logging out of router")
        router.logout()
    return 0


if __name__ == "__main__":
    sys.exit(main())
