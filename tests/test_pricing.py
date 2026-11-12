import pytest

from hba.pricing import price_bill


def test_zero_kwh_is_free():
    assert price_bill(0) == 0


def test_all_tier1():
    assert price_bill(500) == pytest.approx(500 * 0.264 * 1.136)


def test_exactly_at_tier_limit():
    assert price_bill(1000) == pytest.approx(1000 * 0.264 * 1.136)


def test_goes_into_tier2():
    # 1000 at tier 1 + 500 at tier 2
    assert price_bill(1500) == pytest.approx((1000 * 0.264 + 500 * 0.323) * 1.136)
