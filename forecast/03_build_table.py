import glob
import os

import numpy as np
import pandas as pd

from features import make_features   # the same feature code is used for new data

# the forecast folder (where this script is), so it runs from anywhere
ROOT = os.path.dirname(os.path.abspath(__file__))

# ---------------- settings ----------------
# each source: its catalog and the pattern of its storm files
SOURCES = [
    (os.path.join(ROOT, "data", "raw", "GSEP_List.csv"),
     os.path.join(ROOT, "data", "raw", "gsep", "gsep_sc*_ts", "*.csv")),      # 1986-2017
    (os.path.join(ROOT, "data", "raw", "GOESR_List.csv"),
     os.path.join(ROOT, "data", "raw", "goesr_events", "*.csv")),             # 2020-2026, made by 02_detect_events.py
]
SNAPSHOT_HOURS = [0.5, 1, 2, 4, 6]
OUTPUT = os.path.join(ROOT, "data", "processed", "snapshot_table.csv")
STEP_SECONDS = 300  # GOES data are every 5 minutes

# ---------------- catalogs and storm files from all sources ----------------
catalogs = []
files = {}
for catalog_path, files_pattern in SOURCES:
    if not os.path.exists(catalog_path):
        print("Not found, skipping:", catalog_path)
        continue
    one = pd.read_csv(catalog_path)
    one["source"] = os.path.basename(catalog_path).replace("_List.csv", "")
    catalogs.append(one)
    for path in glob.glob(files_pattern):
        name = os.path.basename(path)
        if name.startswith("._"):
            continue
        stem = name[:-4]                                        # e.g. 2017-09-10_04-45
        files[pd.Timestamp(stem[:10] + " " + stem[11:].replace("-", ":"))] = path

catalog = pd.concat(catalogs, ignore_index=True)
for col in ["timestamp", "slice_start", "gsep_max_time"]:
    catalog[col] = pd.to_datetime(catalog[col])
catalog = catalog[catalog["Flag"] == 1]          # only storms above 10 pfu

# solar cycle of each storm, used later to split train and test
year = catalog["timestamp"].dt.year + catalog["timestamp"].dt.month / 12
catalog["cycle"] = np.select([year < 1996.7, year < 2008.9, year < 2019.9],
                             ["SC22", "SC23", "SC24"], default="SC25")

# ---------------- build the snapshot table ----------------
rows = []
skipped = 0
for _, storm in catalog.iterrows():
    if storm["slice_start"] not in files:
        skipped += 1
        continue
    series = pd.read_csv(files[storm["slice_start"]], encoding="utf-8-sig", parse_dates=["time_tag"])
    series = series.set_index("time_tag")
    flux = series.rename(columns={"p3_flux_ic": "p10", "p4_flux_ic": "p30",
                                  "p5_flux_ic": "p50", "p7_flux_ic": "p100"})
    onset = storm["timestamp"]

    # ----- targets: computed once from the WHOLE storm -----
    after = series[series.index >= onset]
    band_10_30 = (after["p3_flux_ic"] - after["p4_flux_ic"]).clip(lower=0)
    band_30_50 = (after["p4_flux_ic"] - after["p5_flux_ic"]).clip(lower=0)
    band_50_100 = (after["p5_flux_ic"] - after["p7_flux_ic"]).clip(lower=0)
    band_100 = after["p7_flux_ic"].clip(lower=0)
    above = after.index[after["p3_flux_ic"] > 10]
    duration_h = (above.max() - onset).total_seconds() / 3600 if len(above) > 0 else 0.0

    log_peak = np.log10(storm["gsep_pf_gt10MeV"])
    log_fluence_10_30 = np.log10((band_10_30 * STEP_SECONDS).sum() + 1)
    log_fluence_30_50 = np.log10((band_30_50 * STEP_SECONDS).sum() + 1)
    log_fluence_50_100 = np.log10((band_50_100 * STEP_SECONDS).sum() + 1)
    log_fluence_100 = np.log10((band_100 * STEP_SECONDS).sum() + 1)

    # ----- one row per snapshot, features use ONLY data up to that moment -----
    for h in SNAPSHOT_HOURS:
        now = onset + pd.Timedelta(hours=h)
        if now > series.index.max():
            continue
        features = make_features(flux, onset, now)
        if features is None:
            continue
        row = {"event": storm["sep_index"], "cycle": storm["cycle"],
               "source": storm["source"], "onset": onset}
        row.update(features)
        row.update({
            "log_peak": log_peak,
            "hours_to_peak": max((storm["gsep_max_time"] - now).total_seconds() / 3600, 0.0),
            "peak_already_passed": int(storm["gsep_max_time"] <= now),
            "duration_h": duration_h,
            "log_fluence_10_30": log_fluence_10_30,
            "log_fluence_30_50": log_fluence_30_50,
            "log_fluence_50_100": log_fluence_50_100,
            "log_fluence_100": log_fluence_100,
        })
        rows.append(row)

table = pd.DataFrame(rows)
os.makedirs(os.path.dirname(OUTPUT), exist_ok=True)
table.to_csv(OUTPUT, index=False)
print("Storms used:", table["event"].nunique(), "| skipped (no file):", skipped)
print("Rows:", len(table))
print(table.groupby(["source", "cycle"])["event"].nunique())
print(table.groupby("hours_since_onset").size())
print(table.head())
