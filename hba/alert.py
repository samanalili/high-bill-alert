import numpy as np
import pandas as pd

from hba import config
from hba.cycles import cycle_end, cycle_length, halfway_day, same_cycle_last_year
from hba.messages import customer_message
from hba.pricing import price_bill


def fit_weather_model(daily):
    # kwh = a + b * max(0, temp - 72), plain least squares
    x = np.maximum(0, daily["temp_f"].values - config.AC_BASE_TEMP_F)
    X = np.column_stack([np.ones(len(x)), x])
    (a, b), *_ = np.linalg.lstsq(X, daily["kwh"].values, rcond=None)
    return a, b


def evaluate(df, cycle_start, day):
    # df: one account's daily data with date, kwh, temp_f
    # day: how many days of this cycle we've seen (day 1 = cycle start)
    daily = df.set_index("date").sort_index()
    start = pd.Timestamp(cycle_start)
    n_days = cycle_length(start)
    ly_start = same_cycle_last_year(start)

    r = {"day": day, "cycle_days": n_days, "halfway_day": halfway_day(start)}

    # need a full year before this cycle (the same cycle last year + the weather fit)
    if daily.index.min() > ly_start:
        r["status"] = "not enough history"
        return r
    if day < config.MIN_DAYS_TO_PROJECT:
        r["status"] = "too early"
        return r

    so_far = daily.loc[start:start + pd.Timedelta(days=day - 1)]
    last_year = daily.loc[ly_start:cycle_end(ly_start)]

    # usage in kWh/day, since cycle lengths vary
    baseline = last_year["kwh"].mean()
    avg_so_far = so_far["kwh"].mean()
    r["baseline_kwh_day"] = baseline
    r["avg_kwh_day"] = avg_so_far
    r["pct_change"] = avg_so_far / baseline - 1

    # price both at current rates over the same number of days
    r["projected_kwh"] = avg_so_far * n_days
    r["last_year_kwh"] = baseline * n_days
    r["projected_bill"] = price_bill(r["projected_kwh"])
    r["last_year_bill"] = price_bill(r["last_year_kwh"])
    r["bill_diff"] = r["projected_bill"] - r["last_year_bill"]
    r["crosses_tier2"] = r["projected_kwh"] > config.TIER1_LIMIT_KWH

    # weather check: fit on the year before this cycle, then ask what that
    # model expects for the temps we've had so far
    fit_days = daily.loc[start - pd.Timedelta(days=365):start - pd.Timedelta(days=1)]
    a, b = fit_weather_model(fit_days)
    cooling = np.maximum(0, so_far["temp_f"].values - config.AC_BASE_TEMP_F)
    expected = (a + b * cooling).mean()
    r["weather_a"], r["weather_b"] = a, b
    r["weather_expected_kwh_day"] = expected
    r["weather_adj_change"] = avg_so_far / expected - 1

    # how much hotter vs the same days of last year's cycle
    r["temp_diff_f"] = so_far["temp_f"].mean() - last_year["temp_f"].iloc[:day].mean()

    r["passes_pct"] = r["pct_change"] > config.PCT_THRESHOLD
    r["passes_dollar"] = r["bill_diff"] > config.DOLLAR_THRESHOLD
    r["would_alert"] = r["passes_pct"] and r["passes_dollar"]
    if r["would_alert"]:
        r["cause"] = "home" if r["weather_adj_change"] > config.PCT_THRESHOLD else "weather"
        r["message"] = customer_message(r)
    else:
        r["cause"] = None
        r["message"] = None

    r["status"] = "ok"
    return r


def alert_decision(df, cycle_start):
    # the official call is made once, at the halfway day
    return evaluate(df, cycle_start, halfway_day(cycle_start))
