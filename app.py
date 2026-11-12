# streamlit front end for the nightly job. run: streamlit run app.py
# all the real logic lives in run_alerts.py, this just runs it and shows what happened

import html
import os

import matplotlib.pyplot as plt
import pandas as pd
import streamlit as st

import run_alerts as ra

THIS_YEAR = "#2a78d6"
LAST_YEAR = "#7a7974"
MUTED = "#52514e"

st.set_page_config(page_title="High Bill Alert job", layout="wide")
st.title("High Bill Alert: nightly job")

# controls up top
c1, c2, c3 = st.columns(3)
run_date = c1.date_input("Run date", pd.Timestamp("2026-08-31"))
pct = c2.slider("Usage up more than (%)", 0, 50, 15)
dollars = c3.slider("Bill up more than ($)", 0, 100, 5)

# the job reads its thresholds from these module constants, so just overwrite them
ra.PCT_THRESHOLD = pct / 100
ra.DOLLAR_THRESHOLD = float(dollars)

b1, b2, _ = st.columns([1, 1, 4])
if b1.button("Run tonight's job", type="primary"):
    st.session_state["results"] = ra.run_nightly(run_date)
    st.session_state["ran_on"] = pd.Timestamp(run_date)

# wipe the outputs so the same date can be rerun from scratch
if b2.button("Reset"):
    for f in [ra.OUT_FILE, ra.SENT_FILE]:
        if os.path.exists(f):
            os.remove(f)
    st.session_state.pop("results", None)
    st.success("Cleared alerts_out.csv and sent_alerts.csv")

if "results" not in st.session_state:
    st.info("Pick a date and hit run.")
    st.stop()

results = st.session_state["results"]
ran_on = st.session_state["ran_on"]
count = lambda kind: sum(x["result"] == kind for x in results)

# summary
st.subheader(f"Results for {ran_on.date()}")
m1, m2, m3, m4 = st.columns(4)
m1.metric("Checked", len(results))
m2.metric("Skipped", count("skipped"))
m3.metric("No alert", count("no alert"))
m4.metric("Alerted", count("alerted"))
if count("already alerted"):
    st.caption(f"{count('already alerted')} already got an alert earlier this cycle, "
               "hit reset to rerun from scratch")

if not results:
    st.write("Nobody is at their halfway day on this date.")
    st.stop()

# every account checked + what happened
left, right = st.columns([3, 2])
with left:
    table = pd.DataFrame(results)[["account_id", "result", "detail"]]
    st.dataframe(table, hide_index=True, use_container_width=True)

# the actual messages, as little text bubbles. $ gets swapped so markdown doesn't treat it as math
with right:
    for x in results:
        if x["result"] != "alerted":
            continue
        msg = html.escape(x["message"]).replace("$", "&#36;")
        st.markdown(
            f"<div style='font-size:.8rem;color:{MUTED}'>{x['account_id']} · via {x['channel']}</div>"
            f"<div style='background:{THIS_YEAR};color:white;padding:10px 14px;border-radius:16px;"
            f"border-bottom-left-radius:4px;margin:2px 0 14px;max-width:420px'>{msg}</div>",
            unsafe_allow_html=True)


# chart: running kWh this cycle vs same cycle last year, plus the projection
st.subheader("This cycle vs last year")
usage, billing, _ = ra.load_data()
acct = st.selectbox("Account", [x["account_id"] for x in results],
                    index=next((i for i, x in enumerate(results) if x["result"] == "alerted"), 0))
row = billing[billing["account_id"] == acct].iloc[0]

n_days = ra.cycle_days(row)
day = (ran_on - row["cycle_start"]).days + 1
r = ra.project(row, usage, ran_on)

mine = usage[usage["account_id"] == acct]
so_far = mine[(mine["date"] >= row["cycle_start"]) & (mine["date"] <= ran_on)]
ly_start = row["cycle_start"] - pd.DateOffset(years=1)
ly_end = row["cycle_end"] - pd.DateOffset(years=1)
last_year = mine[(mine["date"] >= ly_start) & (mine["date"] <= ly_end)]

fig, ax = plt.subplots(figsize=(9, 4))
ax.plot(range(1, len(last_year) + 1), last_year["kwh"].cumsum(), color=LAST_YEAR, lw=2,
        label="Same cycle last year")
ax.plot(range(1, len(so_far) + 1), so_far["kwh"].cumsum(), color=THIS_YEAR, lw=2,
        label="This cycle so far")
ax.plot([day, n_days], [so_far["kwh"].sum(), r["projected_kwh"]], color=THIS_YEAR, lw=2,
        ls="--", label="Projection")

# label the line ends so you don't need the legend
ax.text(n_days, last_year["kwh"].sum(), f" {last_year['kwh'].sum():,.0f} kWh", va="center",
        color=LAST_YEAR, fontsize=9)
ax.text(n_days, r["projected_kwh"], f" {r['projected_kwh']:,.0f} kWh", va="center",
        color=MUTED, fontsize=9)

ax.axhline(ra.TIER_CUTOFF_KWH, color=MUTED, lw=1, ls=":")
ax.text(1, ra.TIER_CUTOFF_KWH, f" tier 2 starts ({ra.TIER_CUTOFF_KWH:,} kWh)", va="bottom",
        color=MUTED, fontsize=9)
ax.axvline(day, color=MUTED, lw=1)
ax.text(day, 0, " tonight", va="bottom", color=MUTED, fontsize=9)

ax.set_xlim(1, n_days)
ax.set_ylim(0, None)
ax.set_xlabel("Day of cycle")
ax.set_ylabel("kWh, running total")
ax.grid(axis="y", alpha=0.3)
ax.spines[["top", "right"]].set_visible(False)
ax.legend(frameon=False, loc="upper left")
fig.tight_layout()
st.pyplot(fig)
st.caption(f"{acct}: projected \\${r['projected_bill']:.0f} vs \\${r['last_year_bill']:.0f} last year "
           f"({r['pct_change'] * 100:+.1f}% usage)")
