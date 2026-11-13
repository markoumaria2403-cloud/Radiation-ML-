# The live forecast. Runs non-stop and every 5 minutes:
#   1. reads the newest proton flux from NOAA (GOES, the same data that
#      NOAA's Space Weather Prediction Center uses for its alerts)
#   2. checks whether a storm is going on
#   3. if yes, describes it with features.py and runs the models of 04_train.py
#   4. prints the forecast, adds it to a log file and redraws one figure
#
# When does it forecast?
#   no storm                      -> "ALL CLEAR", nothing to forecast
#   storm, first 30 minutes       -> "STORM STARTED", wait for the first forecast
#   storm, 30 min to 6 h          -> a new forecast every 5 minutes
#   storm, after 6 h              -> the models were trained up to 6 h, so the
#                                    forecast made at 6 h is kept
#
# MODE = "replay" plays an old storm as if it were happening now (for testing
# and for the demo, because most days there is no storm).
#
# MODE = "live" reads the newest NOAA data and forecasts in real time. It can be run on any day, but it will only forecast when a storm is going on.
# 
# Run:  python forecast/06_live.py      (stop with Ctrl+C)


import os
import pickle
import sys
import time

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FORECAST = os.path.join(ROOT, "forecast")
LIVE = os.path.join(ROOT, "live")
sys.path.append(FORECAST)
from features import GSEP_QUIET, make_features   # the same feature code as in training

MODEL_FILE = os.path.join(FORECAST, "models", "forecast_models.pkl")

MODE = "replay"              # "live" = real NOAA data now, "replay" = an old storm from a file

# --- live ---
LIVE_URL = "https://services.swpc.noaa.gov/json/goes/primary/integral-protons-7-day.json"
CHECK_EVERY_SECONDS = 300    # NOAA publishes a new point every 5 minutes
ENERGIES = {">=10 MeV": "p10", ">=30 MeV": "p30", ">=50 MeV": "p50", ">=100 MeV": "p100"}

# --- replay ---
REPLAY_FILE = os.path.join(FORECAST, "data", "processed", "GOESR", "goesr_goes19_2025-04-01_2026-12-01.csv")
REPLAY_CHANNELS = {"flux_gt10MeV": "p10", "flux_gt30MeV": "p30",
                   "flux_gt50MeV": "p50", "flux_gt100MeV": "p100"}
REPLAY_START = "2026-01-18 12:00"   # the S4 storm of January 2026
REPLAY_END = "2026-01-19 06:00"
REPLAY_SECONDS_PER_STEP = 0.5       # real seconds for each 5 minutes of data

# --- instrument ---
# quiet-Sun level of the instrument (pfu). None = measured automatically:
# the 10th percentile of each channel over the last 7 days.
QUIET = None

# --- storms ---
THRESHOLD = 10          # pfu, NOAA storm level S1
ONSET_POINTS = 3        # 3 x 5 min above the threshold = a storm starts
END_POINTS = 12         # 12 x 5 min below the threshold = the storm is over
FIRST_FORECAST_H = 0.5  # the first forecast, 30 min after onset
MAX_HOURS = 6           # the models were trained up to 6 h after onset

LIVE_FOLDER = os.path.join(LIVE, "data")
LOG_FILE = os.path.join(LIVE_FOLDER, "live_log.csv")
FIGURE_FILE = os.path.join(LIVE, "Figures", "live.png")
LOG_COLUMNS = ["time", "status", "p10_now", "onset", "hours_since_onset",
               "pred_log_peak", "pred_log_fluence_10_30", "pred_log_fluence_30_50",
               "pred_log_fluence_50_100", "pred_log_fluence_100",
               "prob_peak_passed", "prob_peak_within_6h", "outside_training"]
os.makedirs(LIVE_FOLDER, exist_ok=True)
os.makedirs(os.path.dirname(FIGURE_FILE), exist_ok=True)


# LOAD THE MODELS 
with open(MODEL_FILE, "rb") as f:
    saved = pickle.load(f)
features = saved["features"]
ranges = saved["ranges"]

if MODE == "replay":
    replay = pd.read_csv(REPLAY_FILE, parse_dates=["time_tag"])
    replay = replay.rename(columns=REPLAY_CHANNELS).set_index("time_tag")[list(REPLAY_CHANNELS.values())]
    replay = replay.sort_index().resample("5min").mean().interpolate(limit=6)
    now = pd.Timestamp(REPLAY_START)
    print("REPLAY of", REPLAY_START, "to", REPLAY_END)
else:
    print("LIVE from", LIVE_URL)


#  THE LOOP
# REads the data every 5 minutes
while True:

    # a. the last 7 days of flux
    if MODE == "live":
        try:
            raw = pd.read_json(LIVE_URL)
        except Exception as error:
            print("No data from NOAA, trying again in 1 minute:", error)
            time.sleep(60)
            continue
        raw = raw[raw["energy"].isin(ENERGIES.keys())]
        raw["time_tag"] = pd.to_datetime(raw["time_tag"], utc=True).dt.tz_localize(None)   # UTC
        flux = raw.pivot_table(index="time_tag", columns="energy", values="flux").rename(columns=ENERGIES)
        flux = flux[list(ENERGIES.values())].resample("5min").mean().interpolate(limit=6)
        now = flux.index.max()
        delay_min = (pd.Timestamp.utcnow().tz_localize(None) - now).total_seconds() / 60
        if delay_min > 20:
            print(f"Warning: the newest NOAA data are {delay_min:.0f} minutes old")
    else:
        if now > pd.Timestamp(REPLAY_END):
            print("End of the replay.")
            break
        flux = replay.loc[now - pd.Timedelta(days=7):now].copy()

    # move the instrument's quiet level onto GSEP's, like in training
    quiet = flux.quantile(0.10) if QUIET is None else pd.Series(QUIET)
    for col in flux.columns:
        flux[col] = (flux[col] - quiet[col]).clip(lower=0) + GSEP_QUIET[col]
    p10_now = flux["p10"].iloc[-1]

    # b. is a storm going on? walk through the 7 days
    above = (flux["p10"] >= THRESHOLD).values
    onset = None
    below = 0
    for i in range(len(above) - ONSET_POINTS + 1):
        if onset is None:
            if above[i:i + ONSET_POINTS].all():
                onset = flux.index[i]
                below = 0
        else:
            below = 0 if above[i] else below + 1
            if below >= END_POINTS:
                onset = None                       # that storm is over

    # c. forecast
    row = {"time": now, "p10_now": p10_now, "onset": onset}
    print("\n" + "=" * 60)
    print(f"{now:%Y-%m-%d %H:%M} UTC | flux >10 MeV: {p10_now:.1f} pfu")

    if onset is None:
        row["status"] = "ALL CLEAR"
        print("ALL CLEAR: no storm")

    else:
        hours = (now - onset).total_seconds() / 3600
        if hours < FIRST_FORECAST_H:
            row["status"] = "STORM STARTED"
            print(f"STORM STARTED at {onset:%H:%M} UTC. First forecast at "
                  f"{onset + pd.Timedelta(hours=FIRST_FORECAST_H):%H:%M} UTC")
        else:
            # after 6 h the forecast made at 6 h is kept
            model_time = min(now, onset + pd.Timedelta(hours=MAX_HOURS))
            X = pd.DataFrame([make_features(flux, onset, model_time)])[features]

            if X.isna().any(axis=None):
                row["status"] = "NO FORECAST"
                print("Not enough data for a forecast (missing values)")
            else:
                row["status"] = "STORM" if hours <= MAX_HOURS else "STORM (forecast frozen at 6 h)"
                row["hours_since_onset"] = hours
                for target, model in saved["size"].items():
                    row["pred_" + target] = model.predict(X)[0]
                for target, model in saved["time"].items():
                    row["prob_" + target] = model.predict_proba(X)[0, 1]
                row["prob_peak_within_6h"] = max(row["prob_peak_within_6h"], row["prob_peak_passed"])
                model_hours = X["hours_since_onset"].iloc[0]
                if model_hours < 1:                       # not reliable yet (see 04_train.py)
                    row["prob_peak_passed"] = np.nan
                if model_hours < 4:
                    row["prob_peak_within_6h"] = np.nan
                row["outside_training"] = int(((X < ranges.loc["min"]) | (X > ranges.loc["max"])).sum(axis=1).iloc[0])

                peak = 10 ** row["pred_log_peak"]
                s_level = int(np.clip(np.floor(row["pred_log_peak"]), 0, 5))   # NOAA scale: 10 pfu = S1, 100 = S2 ...
                print(f"{row['status']} since {onset:%Y-%m-%d %H:%M} UTC ({hours:.1f} h)")
                print(f"  forecast peak        : {peak:,.0f} pfu  (S{s_level})")
                print(f"  fluence 10-30 MeV    : 10^{row['pred_log_fluence_10_30']:.1f} protons/cm2/sr")
                print(f"  fluence 30-50 MeV    : 10^{row['pred_log_fluence_30_50']:.1f}")
                print(f"  fluence 50-100 MeV   : 10^{row['pred_log_fluence_50_100']:.1f}")
                print(f"  fluence >100 MeV     : 10^{row['pred_log_fluence_100']:.1f}")
                print("  peak already passed  :",
                      "not reliable before 1 h" if np.isnan(row["prob_peak_passed"]) else f"{row['prob_peak_passed']:.0%}")
                print("  peak within 6 h      :",
                      "not reliable before 4 h" if np.isnan(row["prob_peak_within_6h"]) else f"{row['prob_peak_within_6h']:.0%}")
                if row["outside_training"] > 0:
                    print("  WARNING: this storm is outside what the models saw in training, "
                          "the forecast is probably too LOW")

    # d. save: one row in the log, one figure (overwritten each time)
    pd.DataFrame([row], columns=LOG_COLUMNS).to_csv(LOG_FILE, mode="a", header=not os.path.exists(LOG_FILE), index=False)

    last_day = flux.loc[now - pd.Timedelta(hours=24):now]
    fig, ax = plt.subplots(figsize=(10, 4.5))
    ax.plot(last_day.index, last_day["p10"], color="grey", label="measured flux >10 MeV")
    ax.plot(last_day.index, last_day["p100"], color="black", lw=0.8, label="measured flux >100 MeV")
    ax.axhline(THRESHOLD, color="tab:orange", ls=":", label="10 pfu (storm, S1)")
    if "pred_log_peak" in row:
        ax.axhline(10 ** row["pred_log_peak"], color="tab:blue", ls="--", label="forecast peak")
    if onset is not None:
        ax.axvline(onset, color="tab:red", lw=1, label="onset")
        ax.axvline(onset + pd.Timedelta(hours=MAX_HOURS), color="tab:red", ls=":", lw=1, label="onset + 6 h")
    ax.set_yscale("log")
    ax.set_ylabel("pfu")
    ax.set_title(f"{now:%Y-%m-%d %H:%M} UTC: {row['status']}")
    ax.legend(fontsize=8, loc="upper left")
    fig.autofmt_xdate()
    fig.tight_layout()
    fig.savefig(FIGURE_FILE, dpi=110)
    plt.close(fig)

    # e. wait for the next point
    if MODE == "live":
        time.sleep(CHECK_EVERY_SECONDS)
    else:
        now = now + pd.Timedelta(minutes=5)
        time.sleep(REPLAY_SECONDS_PER_STEP)
