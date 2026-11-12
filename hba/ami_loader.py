import pandas as pd

REQUIRED_COLUMNS = ["account_id", "date", "kwh", "temp_f"]


def load_ami_csv(path):
    # stub for real meter reads: one row per account per day.
    # whatever comes out of here can go straight into alert.evaluate()
    df = pd.read_csv(path, parse_dates=["date"])
    missing = [c for c in REQUIRED_COLUMNS if c not in df.columns]
    if missing:
        raise ValueError(f"AMI file is missing columns: {missing}")
    return df[REQUIRED_COLUMNS].sort_values(["account_id", "date"]).reset_index(drop=True)


def split_by_account(df):
    # alert.evaluate() wants one account at a time
    return {acct: g.reset_index(drop=True) for acct, g in df.groupby("account_id")}
