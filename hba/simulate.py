import numpy as np
import pandas as pd

from hba import config

PROFILES = {
    "steady": "Steady usage",
    "ev": "Bought an EV",
    "hot": "Hotter summer",
}


def make_dates():
    return pd.date_range(config.SIM_START, config.SIM_END, freq="D")


def make_weather(dates):
    # seasonal curve peaking around Aug 1 (day 213)
    doy = dates.dayofyear.values
    seasonal = 72 + 11 * np.cos(2 * np.pi * (doy - 213) / 365)

    # noise that carries over, so hot days come in streaks
    rng = np.random.default_rng(config.WEATHER_SEED)
    noise = np.zeros(len(dates))
    n = 0.0
    for i in range(len(dates)):
        n = 0.7 * n + rng.normal(0, 1.6)
        noise[i] = n
    return seasonal + noise


def hot_summer_extra(dates):
    extra = np.zeros(len(dates))

    # smooth sine bump, 0 at Jun 10 and Oct 20 2026, +6.5F in the middle
    start, end = pd.Timestamp("2026-06-10"), pd.Timestamp("2026-10-20")
    mask = (dates >= start) & (dates <= end)
    frac = (dates[mask] - start).days / (end - start).days
    extra[mask] += 6.5 * np.sin(np.pi * frac)

    # 9 day heat wave starting Sep 3, peaks at +6F on day 5
    hw_start = pd.Timestamp("2026-09-03")
    mask = (dates >= hw_start) & (dates < hw_start + pd.Timedelta(days=9))
    k = (dates[mask] - hw_start).days
    extra[mask] += 6 * np.sin(np.pi * (k + 1) / 10)
    return extra


def normal_house_kwh(dates, temps):
    weekend = dates.dayofweek >= 5
    kwh = (16
           + 1.5 * weekend
           + 0.25 * np.maximum(0, 58 - temps)   # a little heating
           + 1.15 * np.maximum(0, temps - 72))  # AC
    rng = np.random.default_rng(config.USAGE_SEED)
    kwh = kwh * (1 + rng.normal(0, 0.07, len(dates)))
    return np.maximum(kwh, 4)


def ev_charging_kwh(dates):
    rng = np.random.default_rng(config.EV_SEED)
    weekend = dates.dayofweek >= 5
    ev = np.where(weekend, 4.0, 10.5) * rng.uniform(0.85, 1.15, len(dates))
    return ev * (dates >= pd.Timestamp("2026-08-09"))


def make_profile(name):
    # same seeds for every profile, so the only difference is the story
    dates = make_dates()
    temps = make_weather(dates)
    if name == "hot":
        temps = temps + hot_summer_extra(dates)

    kwh = normal_house_kwh(dates, temps)
    if name == "ev":
        kwh = kwh + ev_charging_kwh(dates)

    # same columns the real AMI loader returns
    return pd.DataFrame({
        "account_id": f"SIM-{name.upper()}",
        "date": dates,
        "kwh": kwh,
        "temp_f": temps,
    })
