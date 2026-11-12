from pathlib import Path

import pandas as pd

# export column name -> short name we use in code.
# if the export spells something differently, fix it here
COLUMNS = {
    "Read Date": "read_date",
    "Start Date": "start_date",
    "Billing Days": "billing_days",
    "KWH Consumption (Base)": "kwh",
    "Total Electric Revenue": "electric_revenue",
    "Total Amount": "total_amount",
    "Tier1 Usage": "tier1_kwh",
    "Tier2 Usage": "tier2_kwh",
    "Tier1 Revenue": "tier1_revenue",
    "Tier2 Revenue": "tier2_revenue",
}

MAX_NORMAL_BILL_DAYS = 90   # the 2021 118-day bill got split into two rebills
LOW_USAGE_YEAR = 2021       # the one weirdly low bill (about 6.7 kWh/day)
LOW_USAGE_KWH_DAY = 8


def to_number(s):
    # "$1,234.56" -> 1234.56, blanks -> NaN
    return pd.to_numeric(s.astype(str).str.replace(r"[$,]", "", regex=True).str.strip(),
                         errors="coerce")


def load_bills(path):
    path = Path(path)
    if path.suffix.lower() in (".xlsx", ".xls"):
        raw = pd.read_excel(path)   # needs openpyxl; or just save the export as CSV
    else:
        raw = pd.read_csv(path)
    raw.columns = raw.columns.str.strip()

    missing = [c for c in COLUMNS if c not in raw.columns]
    if missing:
        raise ValueError(f"bill export is missing columns: {missing}")
    df = raw[list(COLUMNS)].rename(columns=COLUMNS)

    df["read_date"] = pd.to_datetime(df["read_date"], errors="coerce")
    df["start_date"] = pd.to_datetime(df["start_date"], errors="coerce")
    for col in ["billing_days", "kwh", "electric_revenue", "total_amount",
                "tier1_kwh", "tier2_kwh", "tier1_revenue", "tier2_revenue"]:
        df[col] = to_number(df[col])
    return df


def clean_bills(df):
    df = df.copy()
    n_start = len(df)

    # around 2013 some bills show up twice, once as a $0 placeholder
    df = df[df["total_amount"] != 0]
    n_zero = n_start - len(df)

    # the 118-day 2021 bill that was rebilled as two normal bills
    df = df[df["billing_days"] <= MAX_NORMAL_BILL_DAYS]
    n_long = n_start - n_zero - len(df)

    # older rows have no start date
    no_start = df["start_date"].isna()
    df.loc[no_start, "start_date"] = df.loc[no_start, "read_date"] - pd.to_timedelta(
        df.loc[no_start, "billing_days"], unit="D")

    df["kwh_per_day"] = df["kwh"] / df["billing_days"]

    # keep the low 2021 bill in the table but don't use it as anyone's baseline
    df["exclude_from_baseline"] = ((df["read_date"].dt.year == LOW_USAGE_YEAR)
                                   & (df["kwh_per_day"] < LOW_USAGE_KWH_DAY))

    df = df.sort_values("read_date").reset_index(drop=True)
    print(f"cleaned bills: {n_start} rows in, dropped {n_zero} $0 rows and "
          f"{n_long} long rebills, {no_start.sum()} start dates filled in, "
          f"{df['exclude_from_baseline'].sum()} flagged as not-a-baseline")
    return df


def add_same_cycle_last_year(df, tolerance_days=20):
    # for each bill, find the bill read closest to one year earlier
    df = df.copy()
    baselines = df[~df["exclude_from_baseline"]]
    ly_kwh_day = []
    for read_date in df["read_date"]:
        target = read_date - pd.DateOffset(years=1)
        gap = (baselines["read_date"] - target).abs()
        if len(gap) and gap.min() <= pd.Timedelta(days=tolerance_days):
            ly_kwh_day.append(baselines.loc[gap.idxmin(), "kwh_per_day"])
        else:
            ly_kwh_day.append(None)
    df["ly_kwh_per_day"] = pd.to_numeric(pd.Series(ly_kwh_day, index=df.index))
    df["pct_change"] = df["kwh_per_day"] / df["ly_kwh_per_day"] - 1
    return df


def monthly_seasonality(df):
    # average kWh/day by the month the bill was read, across all years
    ok = df[~df["exclude_from_baseline"]]
    return ok.groupby(ok["read_date"].dt.month)["kwh_per_day"].mean().round(1)
