# every rate and threshold lives here so there's one place to change them

# R-1A pricing, taken off the 9/30/2026 bill
TIER1_LIMIT_KWH = 1000      # first 1000 kWh per bill is tier 1
TIER1_RATE = 0.264          # $/kWh
TIER2_RATE = 0.323          # $/kWh
TAX_MULTIPLIER = 1.136      # taxes and fees on top

# alert rules
PCT_THRESHOLD = 0.15        # usage has to be more than 15% above last year
DOLLAR_THRESHOLD = 5.0      # and the bill has to be more than $5 higher
MIN_DAYS_TO_PROJECT = 7     # don't project anything before day 7
AC_BASE_TEMP_F = 72         # temps above this count as "AC weather"

# billing calendar: 2 month cycles starting on these months
CYCLE_START_MONTHS = [2, 4, 6, 8, 10, 12]

# simulation
SIM_START = "2024-12-01"
SIM_END = "2026-11-30"
WEATHER_SEED = 1
USAGE_SEED = 2
EV_SEED = 3
