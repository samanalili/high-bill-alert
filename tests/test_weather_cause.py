from hba.alert import alert_decision
from hba.simulate import make_profile

AUG = "2026-08-01"


def test_steady_never_alerts():
    df = make_profile("steady")
    for start in ["2025-12-01", "2026-02-01", "2026-04-01", "2026-06-01", AUG, "2026-10-01"]:
        assert not alert_decision(df, start)["would_alert"]


def test_ev_is_home():
    r = alert_decision(make_profile("ev"), AUG)
    assert r["would_alert"]
    assert r["cause"] == "home"


def test_hot_summer_is_weather():
    r = alert_decision(make_profile("hot"), AUG)
    assert r["would_alert"]
    assert r["cause"] == "weather"
    assert abs(r["weather_adj_change"]) < 0.05
