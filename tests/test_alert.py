import pandas as pd

from hba.alert import evaluate

CYCLE = "2026-08-01"


def flat_house(last_year_kwh, this_cycle_kwh):
    # two years of flat usage at 70F, then a different flat level from Aug 1 2026
    dates = pd.date_range("2024-12-01", "2026-11-30", freq="D")
    kwh = [this_cycle_kwh if d >= pd.Timestamp(CYCLE) else last_year_kwh for d in dates]
    return pd.DataFrame({"account_id": "TEST", "date": dates, "kwh": kwh, "temp_f": 70.0})


def test_no_projection_before_day_7():
    r = evaluate(flat_house(20, 30), CYCLE, 6)
    assert r["status"] == "too early"


def test_big_jump_alerts():
    r = evaluate(flat_house(20, 25), CYCLE, 31)   # +25%
    assert r["would_alert"]
    assert r["cause"] == "home"   # temps didn't change, so it can't be weather


def test_small_jump_does_not_alert():
    r = evaluate(flat_house(20, 22), CYCLE, 31)   # +10%
    assert not r["passes_pct"]
    assert not r["would_alert"]


def test_tiny_house_fails_dollar_rule():
    # +30% but on half a kWh/day that's only a few dollars
    r = evaluate(flat_house(0.5, 0.65), CYCLE, 31)
    assert r["passes_pct"]
    assert not r["passes_dollar"]
    assert not r["would_alert"]


def test_not_enough_history():
    df = flat_house(20, 25)
    df = df[df["date"] >= "2025-10-01"]
    assert evaluate(df, CYCLE, 31)["status"] == "not enough history"
