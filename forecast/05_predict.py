import os
import pickle

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns

from features import GSEP_QUIET, make_features   

ROOT = os.path.dirname(os.path.abspath(__file__))
MODEL_FILE = os.path.join(ROOT, "models", "forecast_models.pkl")

# the data 
INPUT_FILE = os.path.join(ROOT, "data", "processed", "GOESR", "goesr_goes19_2025-04-01_2026-12-01.csv")
TIME_COLUMN = "time_tag"
CHANNELS = {"flux_gt10MeV": "p10",       
            "flux_gt30MeV": "p30",
            "flux_gt50MeV": "p50",
            "flux_gt100MeV": "p100"}
START = "2026-01-15"                      
END = "2026-01-25"

#  the instrument 
# quiet-Sun level of YOUR instrument, per channel (pfu). The model was trained on the old
# GOES (GSEP), so other instruments are shifted onto the GSEP levels.
#   GOES-16: {"p10": 0.40, "p30": 0.26, "p50": 0.25, "p100": 0.21}
#   GOES-19: {"p10": 0.37, "p30": 0.24, "p50": 0.23, "p100": 0.21}
#   old GOES / GSEP: None (no change)
QUIET = {"p10": 0.37, "p30": 0.24, "p50": 0.23, "p100": 0.21}

# the storms 
THRESHOLD = 10          
ONSET_POINTS = 3        
END_POINTS = 12         
EVERY_MINUTES = 15      
MAX_HOURS = 6           

OUTPUT_FILE = os.path.join(ROOT, "data", "processed", "forecast_output.csv")
FIGURES = os.path.join(ROOT, "Figures", "forecasts")
os.makedirs(FIGURES, exist_ok=True)


# LOAD THE MODELS
with open(MODEL_FILE, "rb") as f:
    saved = pickle.load(f)
features = saved["features"]
ranges = saved["ranges"]


# LOAD AND CLEAN THE FLUX
flux = pd.read_csv(INPUT_FILE, parse_dates=[TIME_COLUMN])
flux = flux.rename(columns=CHANNELS).set_index(TIME_COLUMN)[list(CHANNELS.values())]
flux = flux.sort_index().resample("5min").mean()       
flux = flux.interpolate(limit=6)                       
if START is not None:
    flux = flux.loc[START:END]

if QUIET is not None:
    for col in flux.columns:
        flux[col] = (flux[col] - QUIET[col]).clip(lower=0) + GSEP_QUIET[col]

print("Data:", flux.index.min(), "to", flux.index.max(), "|", len(flux), "points")


# FIND THE STORMS
above = (flux["p10"] >= THRESHOLD).values
onsets = []
i = 0
while i < len(above) - ONSET_POINTS:
    if above[i:i + ONSET_POINTS].all():
        onsets.append(flux.index[i])
        below = 0
        while i < len(above) and below < END_POINTS:
            below = 0 if above[i] else below + 1
            i += 1
    else:
        i += 1
print("Storms found:", len(onsets), [str(t) for t in onsets])


# FEATURES: every EVERY_MINUTES, from 30 minutes to MAX_HOURS after onset

rows = []
for number, onset in enumerate(onsets):
    times = pd.date_range(onset + pd.Timedelta(minutes=30),
                          min(onset + pd.Timedelta(hours=MAX_HOURS), flux.index.max()),
                          freq=f"{EVERY_MINUTES}min")
    for now in times:
        row = make_features(flux, onset, now)
        if row is None:
            continue
        row["storm"] = f"storm_{number + 1}_{onset:%Y-%m-%d_%H%M}"
        row["onset"] = onset
        row["time"] = now
        rows.append(row)

forecasts = pd.DataFrame(rows).dropna(subset=features)
if len(forecasts) == 0:
    raise SystemExit("No storm with enough data in this period.")


# PREDICT

X = forecasts[features]

for target, model in saved["size"].items():
    forecasts["pred_" + target] = model.predict(X)
forecasts["pred_peak_pfu"] = 10 ** forecasts["pred_log_peak"]

for target, model in saved["time"].items():
    forecasts["prob_" + target] = model.predict_proba(X)[:, 1]
forecasts["prob_peak_within_6h"] = np.maximum(forecasts["prob_peak_within_6h"],
                                              forecasts["prob_peak_passed"])

# hide what was not better than the baseline
forecasts.loc[forecasts["hours_since_onset"] < 1, "prob_peak_passed"] = np.nan
forecasts.loc[forecasts["hours_since_onset"] < 4, "prob_peak_within_6h"] = np.nan

# warn when the data are outside what the models saw in training
outside = (X < ranges.loc["min"]) | (X > ranges.loc["max"])
forecasts["outside_training"] = outside.sum(axis=1)
if forecasts["outside_training"].any():
    print("Warning:", int((forecasts["outside_training"] > 0).sum()),
          "forecasts use values never seen in training (less reliable).")


# SAVE AND PRINT
forecasts.to_csv(OUTPUT_FILE, index=False)
show = ["storm", "hours_since_onset", "pred_peak_pfu", "prob_peak_passed", "prob_peak_within_6h"]
print(forecasts[show][forecasts["hours_since_onset"].isin([0.5, 1, 2, 4, 6])]
      .round(2).to_string(index=False))
print("\nSaved:", OUTPUT_FILE)


# ONE FIGURE PER STORM
sns.set_theme(style="whitegrid")
for storm, g in forecasts.groupby("storm"):
    onset = g["onset"].iloc[0]
    seen = flux.loc[onset - pd.Timedelta(hours=6):onset + pd.Timedelta(hours=48)]
    hours_seen = (seen.index - onset).total_seconds() / 3600

    fig, axes = plt.subplots(1, 2, figsize=(13, 4.8))

    axes[0].plot(hours_seen, seen["p10"], color="grey", lw=1, label="measured flux >10 MeV")
    axes[0].plot(g["hours_since_onset"], g["pred_peak_pfu"], color="tab:blue", marker="o", ms=3,
                 label="forecast of the peak")
    axes[0].axvline(MAX_HOURS, color="k", ls=":", lw=1)
    axes[0].axhline(100, color="tab:orange", ls=":", label="100 pfu (S2)")
    axes[0].set_yscale("log")
    axes[0].set_xlabel("hours since onset")
    axes[0].set_ylabel("pfu")
    axes[0].set_title(storm + ": how big")
    axes[0].legend(fontsize=8)

    axes[1].plot(g["hours_since_onset"], g["prob_peak_passed"], marker="o", ms=3,
                 label="peak already passed")
    axes[1].plot(g["hours_since_onset"], g["prob_peak_within_6h"], marker="o", ms=3,
                 label="peak within 6 h")
    axes[1].set_ylim(0, 1)
    axes[1].set_xlim(0, MAX_HOURS)
    axes[1].set_xlabel("hours since onset")
    axes[1].set_ylabel("probability")
    axes[1].set_title("when (empty = not reliable yet)")
    axes[1].legend(fontsize=8)

    fig.tight_layout()
    fig.savefig(os.path.join(FIGURES, storm + ".png"), dpi=130)
    plt.close(fig)

print("Figures saved in", FIGURES)
