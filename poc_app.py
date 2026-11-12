# streamlit demo: pick a profile and a cycle, then drag the day slider
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import streamlit as st

from hba import config
from hba.alert import alert_decision, evaluate
from hba.cycles import (cycle_end, cycle_label, cycle_length, cycle_starts_between,
                        halfway_day, same_cycle_last_year)
from hba.simulate import PROFILES, make_profile

THIS_YEAR = "#2a78d6"
LAST_YEAR = "#9a9993"
TEMP = "#eb6834"
MUTED = "#52514e"

st.set_page_config(page_title="High Bill Alert", layout="wide")
st.title("High Bill Alert demo")


@st.cache_data
def load_profile(name):
    return make_profile(name)


# --- pickers ---
profile = st.sidebar.selectbox("Customer profile", list(PROFILES), format_func=PROFILES.get)
cycles = cycle_starts_between("2025-12-01", "2026-10-01")
default_cycle = cycles.index(pd.Timestamp("2026-08-01"))
start = st.sidebar.selectbox("Billing cycle", cycles, index=default_cycle, format_func=cycle_label)

n_days = cycle_length(start)
half = halfway_day(start)
day = st.slider("Day of the billing cycle", 1, n_days, half)

df = load_profile(profile)
r = evaluate(df, start, day)
decision = alert_decision(df, start) if day >= half else None

# --- slice out this cycle and last year's ---
daily = df.set_index("date")
this_cycle = daily.loc[start:cycle_end(start)]
so_far = this_cycle.iloc[:day]
ly_start = same_cycle_last_year(start)
last_year = daily.loc[ly_start:cycle_end(ly_start)]
x_now = np.arange(1, day + 1)
x_ly = np.arange(1, len(last_year) + 1)

left, right = st.columns([2, 1])

with left:
    # chart 1: running total this cycle vs last year
    fig, ax = plt.subplots(figsize=(9, 4))
    ax.plot(x_ly, last_year["kwh"].cumsum(), color=LAST_YEAR, lw=2, label="Same cycle last year")
    ax.plot(x_now, so_far["kwh"].cumsum(), color=THIS_YEAR, lw=2, label="This cycle so far")
    if r["status"] == "ok":
        ax.plot([day, n_days], [so_far["kwh"].sum(), r["projected_kwh"]],
                color=THIS_YEAR, lw=2, ls="--", label="Projection")
    ax.axhline(config.TIER1_LIMIT_KWH, color=MUTED, lw=1, ls=":")
    ax.text(1, config.TIER1_LIMIT_KWH, " Tier 2 starts (1000 kWh)", va="bottom", color=MUTED, fontsize=9)
    ax.axvline(half, color=MUTED, lw=1)
    ax.text(half, 0, " halfway: alert day", va="bottom", color=MUTED, fontsize=9)
    ax.set_xlim(1, n_days)
    ax.set_ylim(0, None)
    ax.set_xlabel("Day of cycle")
    ax.set_ylabel("kWh, running total")
    ax.set_title(f"{PROFILES[profile]}: {cycle_label(start)}", loc="left")
    ax.grid(axis="y", alpha=0.3)
    ax.spines[["top", "right"]].set_visible(False)
    ax.legend(frameon=False, loc="upper left")
    st.pyplot(fig)

    # chart 2: daily kWh bars on top, daily high temp underneath on the same days
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(9, 4.5), sharex=True,
                                   gridspec_kw={"height_ratios": [3, 2]})
    ax1.bar(x_now, so_far["kwh"], color=THIS_YEAR, width=0.8, label="This cycle")
    ax1.plot(x_ly, last_year["kwh"], color=LAST_YEAR, lw=1.5, label="Last year")
    ax1.set_ylabel("kWh per day")
    ax1.legend(frameon=False, loc="upper left", ncol=2)
    ax2.plot(x_now, so_far["temp_f"], color=TEMP, lw=2, label="This cycle")
    ax2.plot(x_ly, last_year["temp_f"], color=LAST_YEAR, lw=1.5, label="Last year")
    ax2.axhline(config.AC_BASE_TEMP_F, color=MUTED, lw=1, ls=":")
    ax2.set_ylabel("Daily high (F)")
    ax2.set_xlabel("Day of cycle")
    ax2.legend(frameon=False, loc="upper left", ncol=2)
    for a in (ax1, ax2):
        a.axvline(half, color=MUTED, lw=1)
        a.grid(axis="y", alpha=0.3)
        a.spines[["top", "right"]].set_visible(False)
    ax2.set_xlim(0.5, n_days + 0.5)
    fig.tight_layout()
    st.pyplot(fig)

with right:
    st.subheader(f"Day {day} of {n_days}")

    if r["status"] != "ok":
        st.info(f"Too early to project. We wait until day {config.MIN_DAYS_TO_PROJECT}.")
    else:
        st.metric("Projected bill", f"${r['projected_bill']:.0f}",
                  f"{r['bill_diff']:+.0f} vs last year (${r['last_year_bill']:.0f})",
                  delta_color="inverse")
        st.metric("Usage vs same cycle last year", f"{r['pct_change']:+.0%}",
                  f"{r['avg_kwh_day']:.1f} vs {r['baseline_kwh_day']:.1f} kWh/day",
                  delta_color="off")
        st.metric("After adjusting for weather", f"{r['weather_adj_change']:+.0%}",
                  f"{r['temp_diff_f']:+.1f}F vs last year", delta_color="off")

        st.markdown("**Rules**")
        check = lambda ok: "✅" if ok else "❌"
        st.markdown(
            f"{check(r['passes_pct'])} Usage more than {config.PCT_THRESHOLD:.0%} above last year  \n"
            f"{check(r['passes_dollar'])} Bill more than ${config.DOLLAR_THRESHOLD:.0f} higher  \n"
            f"{check(r['weather_adj_change'] > config.PCT_THRESHOLD)} Still more than "
            f"{config.PCT_THRESHOLD:.0%} after weather (means cause = home)  \n"
            f"{'⚠️' if r['crosses_tier2'] else '➖'} Projection crosses 1000 kWh (Tier 2)"
        )

    st.markdown("**Alert status**")
    if decision is None:
        if r["status"] == "ok" and r["would_alert"]:
            st.warning(f"Tracking: on pace to alert ({r['cause']}). Decision on day {half}.")
        else:
            st.write(f"Waiting for day {half} to decide.")
    elif decision["would_alert"]:
        st.error(f"Alert sent on day {half}. Cause: {decision['cause']}")
        st.markdown("**Customer message**")
        st.write(decision["message"])
    else:
        st.success(f"No alert. Day {half} check passed.")
