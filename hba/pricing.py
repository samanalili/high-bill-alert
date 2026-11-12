from hba import config


def price_bill(kwh):
    # first 1000 kWh at tier 1, anything above at tier 2, then taxes and fees
    tier1_kwh = min(kwh, config.TIER1_LIMIT_KWH)
    tier2_kwh = max(0, kwh - config.TIER1_LIMIT_KWH)
    energy = tier1_kwh * config.TIER1_RATE + tier2_kwh * config.TIER2_RATE
    return energy * config.TAX_MULTIPLIER
