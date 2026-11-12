# just the facts: how much higher, what the bill looks like, and tier 2 if it applies.
# the cause (weather vs home) stays internal, it's shown in the app but not sent
def customer_message(r):
    pct = r["pct_change"] * 100
    msg = (f"Your electricity use this billing period is running about {pct:.0f}% higher "
           f"than the same period last year. At this pace your bill will be around "
           f"${r['projected_bill']:.0f}, compared to ${r['last_year_bill']:.0f} last year.")

    if r["crosses_tier2"]:
        msg += (" You're on track to use over 1,000 kWh, and usage above that is billed "
                "at the higher Tier 2 rate.")
    return msg
