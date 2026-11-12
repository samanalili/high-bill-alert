# runs every second-year cycle for each simulated profile at the halfway day,
# then sanity checks the real bill export if one is in data/raw
from pathlib import Path

import pandas as pd

from hba import config
from hba.alert import alert_decision
from hba.cycles import cycle_label, cycle_starts_between
from hba.pricing import price_bill
from hba.real_bills import add_same_cycle_last_year, clean_bills, load_bills, monthly_seasonality
from hba.simulate import PROFILES, make_profile

RAW_DIR = Path(__file__).parent / "data" / "raw"


def run_simulated():
    cycles = cycle_starts_between("2025-12-01", "2026-10-01")
    rows = []
    for name, label in PROFILES.items():
        df = make_profile(name)
        for start in cycles:
            r = alert_decision(df, start)
            rows.append({
                "profile": label,
                "cycle": cycle_label(start),
                "day": f"{r['halfway_day']}/{r['cycle_days']}",
                "pct change": f"{r['pct_change']:+.0%}",
                "projected bill": f"${r['projected_bill']:.0f}",
                "last year": f"${r['last_year_bill']:.0f}",
                "hotter by": f"{r['temp_diff_f']:+.1f}F",
                "weather adj": f"{r['weather_adj_change']:+.0%}",
                "alert": "YES" if r["would_alert"] else "no",
                "cause": r["cause"] or "",
                "tier 2": "yes" if r["crosses_tier2"] else "",
            })
    print(pd.DataFrame(rows).to_string(index=False))

    # print one example of each message so we can read them
    for name, start in [("ev", "2026-08-01"), ("hot", "2026-08-01")]:
        r = alert_decision(make_profile(name), start)
        print(f"\n{PROFILES[name]}, {cycle_label(start)} message:\n  {r['message']}")


def run_real():
    files = [p for p in RAW_DIR.iterdir() if p.suffix.lower() in (".csv", ".xlsx", ".xls")]
    if not files:
        print("\n(no bill export in data/raw yet, skipping real data check)")
        return
    print(f"\n=== real bills: {files[0].name} ===")
    bills = add_same_cycle_last_year(clean_bills(load_bills(files[0])))

    print("\navg kWh/day by read month (seasonality check):")
    print(monthly_seasonality(bills).to_string())

    print("\nlast 8 bills vs same cycle last year:")
    recent = bills.tail(8).copy()
    recent["flag"] = recent["pct_change"] > config.PCT_THRESHOLD
    cols = ["start_date", "read_date", "billing_days", "kwh", "kwh_per_day",
            "ly_kwh_per_day", "pct_change", "flag"]
    print(recent[cols].round(3).to_string(index=False))

    # pricing check on the most recent bill (older bills used older rates)
    last = bills.iloc[-1]
    ours = price_bill(last["kwh"])
    print(f"\npricing check, bill read {last['read_date']:%m/%d/%Y}, {last['kwh']:.0f} kWh:")
    print(f"  our energy charge before tax: ${ours / config.TAX_MULTIPLIER:.2f}   "
          f"bill tier1+tier2 revenue: ${last['tier1_revenue'] + last['tier2_revenue']:.2f}")
    print(f"  our total with tax/fees:     ${ours:.2f}   "
          f"bill total electric revenue: ${last['electric_revenue']:.2f}")


if __name__ == "__main__":
    run_simulated()
    run_real()
