import logging
import sys

from .config import load_config
from .poller import Poller
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
    router = LibRouterClient(
        host=cfg.host,
        password=cfg.password,
        auth_backoff_seconds=cfg.auth_backoff_seconds,
        stale_session_threshold=cfg.stale_session_threshold,
    )
    Poller(router, store).run_forever(cfg.poll_interval)
    return 0


if __name__ == "__main__":
    sys.exit(main())
