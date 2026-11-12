# nightly high bill alert job (MVP)
# run it like: python run_alerts.py 2026-08-31
#
# every night, check everyone who's halfway through their billing cycle, guess
# their bill, and if it'ss higher than the same cycle last year, queue an alert.
# nothing actually gets sent yet, alerts just go into a csv for the CRM

# Example alert: Your electricity use this billing period is running about 34% higher than 
  # the same period last year. At this pace your bill will be around $547, 
  # compared to $392 last year. You're on track to use over 1,000 kWh, and usage
  # above that is billed at the higher Tier 2 rate.

import math
import os
import sys

import pandas as pd

# reusing the POC: price_bill() turns kWh into dollars, customer_message() writes the alert text
from hba import config
from hba.messages import customer_message
from hba.pricing import price_bill

# rates (R-1A, off the 9/30/2026 bill). first 1000 kWh is tier 1, the rest is tier 2
TIER_CUTOFF_KWH = 1000
TIER1_PRICE = 0.264     # $/kWh
TIER2_PRICE = 0.323     # $/kWh

# alert rules, both have to be true
PCT_THRESHOLD = 0.15    # usage up more than 15%
DOLLAR_THRESHOLD = 5.0  # bill up more than $5 so small bills don't alert over pennies
MIN_YEARS_HISTORY = 2   # newer customers don't have a fair last year to compare to

# inputs are fake stand-ins for MDMS + billing
DATA = "data"
USAGE_FILE = os.path.join(DATA, "mdms_daily_usage.csv")
BILLING_FILE = os.path.join(DATA, "billing.csv")
SENT_FILE = os.path.join(DATA, "sent_alerts.csv")   # who already got alerted
OUT_FILE = os.path.join(DATA, "alerts_out.csv")     # the "CRM inbox"

# price_bill() reads rates from hba/config, so copy ours over or changing them up top does nothing
config.TIER1_LIMIT_KWH = TIER_CUTOFF_KWH
config.TIER1_RATE = TIER1_PRICE
config.TIER2_RATE = TIER2_PRICE


# step 1: load everything
def load_data():
    usage = pd.read_csv(USAGE_FILE, parse_dates=["date"])
    billing = pd.read_csv(BILLING_FILE, parse_dates=["cycle_start", "cycle_end"])

    # no sent log until the first alert goes out, so start empty
    if os.path.exists(SENT_FILE):
        sent = pd.read_csv(SENT_FILE, parse_dates=["cycle_start"])
    else:
        sent = pd.DataFrame(columns=["account_id", "cycle_start", "sent_on"])
    return usage, billing, sent


# step 2: who's due tonight
def cycle_days(row):
    # +1 since both ends count (aug 1 to sep 30 is 61 days)
    return (row["cycle_end"] - row["cycle_start"]).days + 1


def is_halfway(row, run_date):
    # day 1 = cycle start. halfway = days / 2 rounded up, so day 31 of 61 (same as POC)
    day = (run_date - row["cycle_start"]).days + 1
    return day == math.ceil(cycle_days(row) / 2)


# step 3: who we don't alert. returns the reason, or None if they're fine
def skip_reason(row):
    if row["customer_type"] != "residential":
        return "not residential"
    if row["years_of_history"] < MIN_YEARS_HISTORY:
        return "under 2 years of history"
    if row["opted_out"]:
        return "opted out"
    return None


# steps 4 + 5: guess the bill and compare to last year
def project(row, usage, run_date):
    # this account's usage from cycle start up to tonight
    mine = usage[(usage["account_id"] == row["account_id"])
                 & (usage["date"] >= row["cycle_start"])
                 & (usage["date"] <= run_date)]

    # if they keep going at this pace, here's where they end up
    projected_kwh = mine["kwh"].mean() * cycle_days(row)
    projected_bill = price_bill(projected_kwh)

    # customer_message() needs these exact keys
    r = {
        "projected_kwh": projected_kwh,
        "projected_bill": projected_bill,
        "last_year_bill": row["last_year_bill"],
        "pct_change": projected_kwh / row["last_year_kwh"] - 1,   # 0.34 = up 34%
        "bill_diff": projected_bill - row["last_year_bill"],
        "crosses_tier2": projected_kwh > TIER_CUTOFF_KWH,         # adds a tier 2 warning
    }
    r["alert"] = r["pct_change"] > PCT_THRESHOLD and r["bill_diff"] > DOLLAR_THRESHOLD
    return r


# step 6: one alert per cycle
def already_sent(sent, row):
    hits = sent[(sent["account_id"] == row["account_id"])
                & (sent["cycle_start"] == row["cycle_start"])]
    return len(hits) > 0


# step 7: "send" to CRM. really just appending to a csv, header only if the file is new
def send_to_crm(alerts, run_date):
    out = pd.DataFrame(alerts)
    out.insert(0, "run_date", run_date.date())
    out.to_csv(OUT_FILE, mode="a", header=not os.path.exists(OUT_FILE), index=False)


# log account + cycle so already_sent() catches them next time
def mark_sent(alerts, run_date, cycle_starts):
    rows = pd.DataFrame({"account_id": [a["account_id"] for a in alerts],
                         "cycle_start": cycle_starts,
                         "sent_on": run_date.date()})
    rows.to_csv(SENT_FILE, mode="a", header=not os.path.exists(SENT_FILE), index=False)


# the main job, runs all the steps in order
def run_nightly(run_date):
    run_date = pd.Timestamp(run_date)
    usage, billing, sent = load_data()

    due = billing[billing.apply(is_halfway, axis=1, run_date=run_date)]

    # one row per account checked, the app shows these too
    results = []
    alerts, alert_cycles = [], []

    # each check either records a result and moves on, or lets the account through
    for _, row in due.iterrows():
        acct = row["account_id"]

        reason = skip_reason(row)
        if reason:
            results.append({"account_id": acct, "result": "skipped", "detail": reason})
            continue

        r = project(row, usage, run_date)
        pct = f"usage {r['pct_change'] * 100:+.1f}%"
        if not r["alert"]:
            results.append({"account_id": acct, "result": "no alert", "detail": pct})
            continue

        if already_sent(sent, row):
            results.append({"account_id": acct, "result": "already alerted",
                            "detail": f"{pct}, already alerted this cycle"})
            continue

        # made it through everything, build the alert
        alert = {
            "account_id": acct,
            "channel": row["contact_pref"],
            "projected_bill": round(r["projected_bill"], 2),
            "last_year_bill": round(r["last_year_bill"], 2),
            "pct_change": round(r["pct_change"] * 100, 1),
            "message": customer_message(r),
        }
        alerts.append(alert)
        alert_cycles.append(row["cycle_start"].date())
        results.append({"account_id": acct, "result": "alerted",
                        "detail": f"{pct}, ${alert['projected_bill']:.0f} vs "
                                  f"${alert['last_year_bill']:.0f}, via {alert['channel']}",
                        "channel": alert["channel"], "message": alert["message"]})

    if alerts:
        send_to_crm(alerts, run_date)
        mark_sent(alerts, run_date, alert_cycles)

    print_summary(run_date, results)
    return results


# print a quick summary so can see what happened
def print_summary(run_date, results):
    print(f"run date {run_date.date()}: {len(results)} accounts at their halfway day")
    for kind in ["skipped", "no alert", "already alerted", "alerted"]:
        rows = [x for x in results if x["result"] == kind]
        if kind == "already alerted" and not rows:
            continue
        print(f"  {kind}: {len(rows)}")
        for x in rows:
            print(f"    {x['account_id']}  {x['detail']}")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("usage: python run_alerts.py YYYY-MM-DD")
        sys.exit(1)
    run_nightly(sys.argv[1])
