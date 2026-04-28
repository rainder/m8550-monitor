from dataclasses import dataclass


@dataclass(frozen=True)
class RateInputs:
    prev_ts: int | None
    prev_total: int | None
    ts: int
    total: int


def compute_rate(inputs: RateInputs, max_gap_seconds: int = 10) -> int | None:
    """Bytes per second between two cumulative readings, or None if invalid.

    Returns None when:
    - There is no previous reading (first sample for this counter).
    - dt <= 0 (clock didn't advance).
    - dt exceeds max_gap_seconds (too long since last reading).
    - The counter went down (router/host reboot).
    """
    if inputs.prev_ts is None or inputs.prev_total is None:
        return None
    dt = inputs.ts - inputs.prev_ts
    if dt <= 0 or dt > max_gap_seconds:
        return None
    delta = inputs.total - inputs.prev_total
    if delta < 0:
        return None
    return int(delta / dt)
