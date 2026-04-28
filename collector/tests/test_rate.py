from m8550_collector.rate import compute_rate, RateInputs


def test_compute_rate_normal_delta():
    r = compute_rate(RateInputs(prev_ts=100, prev_total=1000, ts=110, total=2000))
    assert r == 100  # (2000 - 1000) / (110 - 100)


def test_compute_rate_counter_reset_returns_none():
    r = compute_rate(RateInputs(prev_ts=100, prev_total=2000, ts=110, total=500))
    assert r is None


def test_compute_rate_no_previous_returns_none():
    r = compute_rate(RateInputs(prev_ts=None, prev_total=None, ts=110, total=2000))
    assert r is None


def test_compute_rate_dt_zero_returns_none():
    r = compute_rate(RateInputs(prev_ts=100, prev_total=1000, ts=100, total=2000))
    assert r is None


def test_compute_rate_gap_too_large_returns_none():
    # gap of 30s, max allowed gap = 10s
    r = compute_rate(
        RateInputs(prev_ts=100, prev_total=1000, ts=130, total=4000),
        max_gap_seconds=10,
    )
    assert r is None


def test_compute_rate_truncates_to_int():
    r = compute_rate(RateInputs(prev_ts=100, prev_total=1000, ts=103, total=1500))
    # (500 / 3) = 166.66...
    assert r == 166
