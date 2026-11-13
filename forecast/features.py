import numpy as np
import pandas as pd

FEATURES = ["hours_since_onset", "log_p10_now", "log_p30_now", "log_p50_now", "log_p100_now",
            "rise_per_hour", "hardness", "log_max_so_far", "below_max_so_far", "log_background"]

FLOOR = 1e-3        

GSEP_QUIET = {"p10": 0.107, "p30": 0.052, "p50": 0.029, "p100": 0.013}


def make_features(flux, onset, now):
    """
    flux : DataFrame indexed by time (every 5 min), columns p10, p30, p50, p100 in pfu
           (proton flux above 10, 30, 50 and 100 MeV)
    onset: time the storm started (flux > 10 pfu)
    now  : the moment of the forecast

    Returns a dict with the 10 features, using ONLY data up to `now`,
    or None if there is not enough data yet.
    """
    p10 = flux["p10"].clip(lower=FLOOR)
    p30 = flux["p30"].clip(lower=FLOOR)
    p50 = flux["p50"].clip(lower=FLOOR)
    p100 = flux["p100"].clip(lower=FLOOR)

    since_onset = p10[(p10.index >= onset) & (p10.index <= now)]
    if len(since_onset) < 2:
        return None
    before = p10[(p10.index < onset) & (p10.index >= onset - pd.Timedelta(hours=12))]
    p10_now = p10.asof(now)
    p10_half_hour_ago = p10.asof(now - pd.Timedelta(minutes=30))

    return {
        "hours_since_onset": (now - onset).total_seconds() / 3600,
        "log_p10_now": np.log10(p10_now),
        "log_p30_now": np.log10(p30.asof(now)),
        "log_p50_now": np.log10(p50.asof(now)),
        "log_p100_now": np.log10(p100.asof(now)),
        "rise_per_hour": (np.log10(p10_now) - np.log10(p10_half_hour_ago)) / 0.5,
        "hardness": np.log10(p100.asof(now) / p10_now),
        "log_max_so_far": np.log10(since_onset.max()),
        "below_max_so_far": np.log10(since_onset.max() / p10_now),
        "log_background": np.log10(before.median()) if len(before) > 0 else np.nan,
    }
