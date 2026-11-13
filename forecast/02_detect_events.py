import glob
import os

import numpy as np
import pandas as pd


ROOT = os.path.dirname(os.path.abspath(__file__))

#  settings 
INPUT_FILES = glob.glob(os.path.join(ROOT, "data", "processed", "GOESR", "goesr_goes*_*.csv"))
GSEP_CATALOG = os.path.join(ROOT, "data", "raw", "GSEP_List.csv")
GSEP_FOLDER = os.path.join(ROOT, "data", "raw", "gsep")
EVENT_FOLDER = os.path.join(ROOT, "data", "raw", "goesr_events")
CATALOG_OUT = os.path.join(ROOT, "data", "raw", "GOESR_List.csv")

THRESHOLD = 10          # pfu, the NOAA storm threshold (same as GSEP)
ONSET_POINTS = 3        # 3 x 5 min = 15 min above the threshold to start a storm
END_POINTS = 12         # 12 x 5 min = 1 hour below the threshold to end a storm
NEW_RISE = np.log10(3)  # a rise of x3 within 1 hour, after a decay, starts a new storm
DECAY = np.log10(2)     # ... but only if the flux first fell to half of its maximum

CHANNELS = {"flux_gt10MeV": "p3_flux_ic", "flux_gt30MeV": "p4_flux_ic",
            "flux_gt50MeV": "p5_flux_ic", "flux_gt100MeV": "p7_flux_ic"}

#  1. quiet level of GSEP (the reference)
# GOES-R (GOES-16, GOES-19) and the old GOES used in GSEP are different instruments:
# GOES-R reads a higher flux when the Sun is quiet. We will move each GOES-R channel's
# quiet level onto GSEP's, separately for each satellite.
gsep = pd.read_csv(GSEP_CATALOG)
for col in ["timestamp", "slice_start"]:
    gsep[col] = pd.to_datetime(gsep[col])
gsep_files = {}
for path in glob.glob(os.path.join(GSEP_FOLDER, "gsep_sc*_ts", "*.csv")):
    name = os.path.basename(path)
    if not name.startswith("._"):
        stem = name[:-4]
        gsep_files[pd.Timestamp(stem[:10] + " " + stem[11:].replace("-", ":"))] = path
quiet = []
for _, storm in gsep[gsep["Flag"] == 1].iterrows():
    if storm["slice_start"] in gsep_files:
        series = pd.read_csv(gsep_files[storm["slice_start"]], encoding="utf-8-sig", parse_dates=["time_tag"])
        quiet.append(series[series["time_tag"] < storm["timestamp"]][list(CHANNELS.values())])
gsep_floor = pd.concat(quiet).quantile(0.10)
print("Quiet level GSEP:", gsep_floor.round(3).to_dict())

# 2. load each GOES-R file and match its quiet level to GSEP
if len(INPUT_FILES) == 0:
    raise SystemExit("No goesr_*.csv in data/processed/GOESR. Run 01_download_goesr.py first.")
parts = []
for path in sorted(INPUT_FILES):
    part = pd.read_csv(path, parse_dates=["time_tag"]).rename(columns=CHANNELS)
    part_floor = part[list(CHANNELS.values())].quantile(0.10)
    print("Quiet level", os.path.basename(path), ":", part_floor.round(3).to_dict())
    for col in CHANNELS.values():
        part[col] = (part[col] - part_floor[col]).clip(lower=0) + gsep_floor[col]
    parts.append(part)

# a short test file inside a longer download repeats its rows: keep the first copy
goesr = pd.concat(parts).drop_duplicates("time_tag").sort_values("time_tag")
goesr = goesr.set_index("time_tag").resample("5min").mean()
goesr = goesr.interpolate(limit=6)              # fill gaps up to 30 min, like GSEP
print("GOES-R series:", goesr.index.min(), "to", goesr.index.max(), "|", len(goesr), "points")

#  3. find the storms 
p10 = goesr["p3_flux_ic"].rolling(3, center=True, min_periods=1).median()  
p30 = goesr["p4_flux_ic"].rolling(3, center=True, min_periods=1).median()
log10 = np.log10(p10.clip(lower=1e-3)).values
log30 = np.log10(p30.clip(lower=1e-3)).values
times = p10.index
above = (p10 >= THRESHOLD).values

storms = []           
i = 0
n = len(p10)
while i < n - ONSET_POINTS:
    if not above[i:i + ONSET_POINTS].all():
        i += 1
        continue
    onset = i
    j = i
    below_run = 0
    max_log = log10[i]
    min_since_max = log10[i]
    min_index = i
    while j < n:
        if above[j]:
            below_run = 0
        else:
            below_run += 1
            if below_run >= END_POINTS:
                break
        if log10[j] > max_log:
            max_log = log10[j]
            min_since_max = log10[j]
            min_index = j
        if log10[j] < min_since_max:
            min_since_max = log10[j]
            min_index = j
        # a new storm on top of the old one: the >10 MeV flux first fell to half of its max,
        # then the >10 MeV or the >30 MeV flux rose x3 within the last hour
        hour_ago = max(j - 12, onset)
        fell = max_log - min_since_max >= DECAY
        rose10 = log10[j] - log10[hour_ago:j + 1].min() >= NEW_RISE
        rose30 = (log30[j] - log30[hour_ago:j + 1].min() >= NEW_RISE) and (p30.iloc[j] >= 1)
        if fell and (rose10 or rose30) and above[j]:
            if rose30:
                new_onset = hour_ago + int(np.argmin(log30[hour_ago:j + 1]))
            else:
                new_onset = min_index
            if new_onset > onset:
                storms.append([onset, new_onset])
                onset = new_onset
                max_log = log10[j]
                min_since_max = log10[j]
                min_index = j
        j += 1
    end = j - below_run if below_run >= END_POINTS else min(j, n - 1)
    storms.append([onset, end])
    i = j + 1

# a storm that starts less than 12 hours after the previous one ended is its tail
# (storms split above touch each other, gap = 0, so they stay apart)
merged = []
for onset, end in storms:
    if len(merged) > 0:
        gap_h = (times[onset] - times[merged[-1][1]]).total_seconds() / 3600
        if 0 < gap_h < 12:
            merged[-1][1] = end
            continue
    merged.append([onset, end])
# drop blips shorter than 1 hour
storms = [s for s in merged if (times[s[1]] - times[s[0]]).total_seconds() / 3600 >= 1]

#4. write a catalog and one file per storm, in GSEP format 
os.makedirs(EVENT_FOLDER, exist_ok=True)
rows = []
for k, (onset, end) in enumerate(storms):
    t_onset = times[onset]
    t_end = times[end]
    window = goesr["p3_flux_ic"].iloc[onset:end + 1]     # unsmoothed, like the GSEP peak
    t_peak = window.idxmax()
    slice_start = t_onset - pd.Timedelta(hours=12)
    slice_end = t_end + pd.Timedelta(hours=1)
    piece = goesr.loc[slice_start:slice_end].reset_index()
    piece.to_csv(os.path.join(EVENT_FOLDER, slice_start.strftime("%Y-%m-%d_%H-%M") + ".csv"), index=False)
    rows.append({"sep_index": f"goesr_{k + 1:03d}",
                 "timestamp": t_onset,
                 "gsep_max_time": t_peak,
                 "gsep_pf_gt10MeV": window.max(),
                 "slice_start": slice_start,
                 "slice_end": slice_end,
                 "Flag": 1,
                 "duration_h": (t_end - t_onset).total_seconds() / 3600})

catalog = pd.DataFrame(rows)
catalog.to_csv(CATALOG_OUT, index=False)
print("\nStorms found:", len(catalog))
print(catalog[["sep_index", "timestamp", "gsep_max_time", "gsep_pf_gt10MeV", "duration_h"]].to_string(index=False, float_format="%.1f"))
print("\nSaved", CATALOG_OUT, "and", len(catalog), "files in", EVENT_FOLDER)
