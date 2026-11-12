# High Bill Alert (LADWP proof of concept)

Warns residential customers at the halfway point of a billing cycle when they're on pace
for a bill much higher than the same cycle last year, and says whether it looks like
weather or something at home.

## Setup

    conda activate high-bill-alert     # or: pip install -r requirements.txt

## Run

    python backtest.py                 # table of every second-year cycle at the halfway day
    streamlit run poc_app.py           # the POC demo with the day slider
    python -m pytest -q                # tests

Put the real bill export (CSV) in `data/raw/` and `backtest.py` will check it too.
If the column names don't match, fix the `COLUMNS` map at the top of `hba/real_bills.py`.

## Nightly alert job (MVP)

    python run_alerts.py 2026-08-31

This is a separate script from the demo. It reads two fake CSVs in `data/` that stand in for the
real systems, and it doesn't use any weather data.

- `mdms_daily_usage.csv`: daily kWh per account for this cycle and the same cycle last year
  (stands in for MDMS)
- `billing.csv`: one row per account with the current cycle dates, last year's kWh and bill for
  the same cycle, years of history, opt-out flag, and how they want to be contacted

What happens when it runs:

1. **Load** both CSVs, plus `sent_alerts.csv` if it exists.
2. **Find who's due.** Only accounts whose cycle is at its halfway day on the run date get checked.
   For a 61-day cycle starting Aug 1, that's day 31 (Aug 31).
3. **Skip** anyone who isn't residential, has under 2 years of history, or opted out.
4. **Project the bill.** Average kWh/day so far × days in the cycle, priced with the 2-tier rate
   (same `price_bill()` as the POC, so taxes and fees are included).
5. **Compare to last year.** Alert only if usage is up more than 15% *and* the bill is up more than $5.
6. **One alert per cycle.** If the account is already in `sent_alerts.csv` for this cycle, skip it.
7. **"Send to CRM."** Nothing actually gets sent. Each alert is added to `data/alerts_out.csv`
   (account, channel, projected bill, last year's bill, % change, message), the account is logged in
   `sent_alerts.csv`, and a summary prints.

Rates and thresholds are constants at the top of `run_alerts.py`. To run the same date again from
scratch, delete `data/alerts_out.csv` and `data/sent_alerts.csv`.

### Front end

    streamlit run app.py

A page for running the same job by clicking instead of typing. It uses the functions in
`run_alerts.py`, so the logic is the same.

- Pick a run date and hit **Run tonight's job**.
- The sliders change the usage and dollar thresholds, so you can show how that changes who gets
  an alert. Move them and hit run again.
- The top shows how many accounts were checked, skipped, not alerted, and alerted. Under that is a
  table with each account's result, and each alert's message shown as a text bubble.
- The chart shows one account's running kWh this cycle vs the same cycle last year, with the
  projection to the end of the cycle as a dashed line.
- **Reset** deletes `alerts_out.csv` and `sent_alerts.csv` so you can rerun the same date from scratch.

The sample data has 7 accounts: bought an EV (alerts), hot summer (alerts, no weather check yet),
steady, just under 15%, under 2 years of history, commercial, and opted out.
