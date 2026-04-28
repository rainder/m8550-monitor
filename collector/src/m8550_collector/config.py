import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Config:
    host: str
    password: str
    db_path: str
    poll_interval: int


def load_config() -> Config:
    return Config(
        host=os.environ["M8550_HOST"],
        password=os.environ["M8550_PASSWORD"],
        db_path=os.environ["DB_PATH"],
        poll_interval=int(os.environ.get("POLL_INTERVAL", "5")),
    )
