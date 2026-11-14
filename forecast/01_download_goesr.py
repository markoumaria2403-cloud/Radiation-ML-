import os
import re
import time
import warnings

import numpy as np
import pandas as pd
import requests
import xarray as xr

# low-energy channels read 0 when the Sun is quiet; that only triggers harmless warnings
warnings.filterwarnings("ignore", category=RuntimeWarning)


ROOT = os.path.dirname(os.path.abspath(__file__))

SATELLITE = "goes19"
START = "2025-04-01"
END = "2026-12-01"
FOLDER = os.path.join(ROOT, "data", "raw", "goesr")

BASE = ("https://data.ngdc.noaa.gov/platforms/solar-space-observing-satellites/goes/"
        + SATELLITE + "/l2/data/sgps-l2-avg5m/")
SAT_CODE = "g" + SATELLITE[-2:]   # goes16 -> g16, used in the file names


low_mev = np.array([1.0, 1.9, 2.3, 3.4, 6.5, 12, 25, 40, 83, 99, 118, 150, 275])
high_mev = np.array([1.9, 2.3, 3.4, 6.5, 12, 25, 40, 80, 99, 118, 150, 275, 500])
thresholds = [10, 30, 50, 100]  # same as GSEP p3, p4, p5, p7

os.makedirs(FOLDER, exist_ok=True)

#part 1: download the daily files 
months = pd.date_range(START, END, freq="MS")[:-1]
for month in months:
    folder_url = BASE + month.strftime("%Y/%m/")
    listing = requests.get(folder_url, timeout=60)
    if listing.status_code != 200:
        print("No data on the server for", month.strftime("%Y-%m"), "- skipping")
        continue
    names = sorted(set(re.findall(r'href="(sci_sgps-l2-avg5m_[^"]+\.nc)"', listing.text)))
    missing = [n for n in names if not os.path.exists(os.path.join(FOLDER, n))]
    print(month.strftime("%Y-%m"), ":", len(names), "files,", len(missing), "to download", flush=True)
    for i, name in enumerate(missing, 1):
        path = os.path.join(FOLDER, name)
        for attempt in range(3):          # retry a few times on network hiccups
            try:
                file = requests.get(folder_url + name, timeout=120)
                file.raise_for_status()
                break
            except requests.RequestException as err:
                print("   retry", attempt + 1, name, "-", err, flush=True)
                time.sleep(5)
        else:
            print("   FAILED, skipping", name, flush=True)
            continue
        with open(path + ".part", "wb") as f:   # write then rename, so a stopped run
            f.write(file.content)               # never leaves a half-written .nc file
        os.replace(path + ".part", path)
        print(f"   {i}/{len(missing)} {name}", flush=True)
        time.sleep(0.5)

# part 2: turn the files of THIS period into one table 
start_day = pd.Timestamp(START)
end_day = pd.Timestamp(END)
files = []
for name in sorted(os.listdir(FOLDER)):
    found = re.search(r"_" + SAT_CODE + r"_d(\d{8})_", name)
    if found is None:
        continue
    day = pd.to_datetime(found.group(1), format="%Y%m%d")
    if start_day <= day < end_day:
        files.append(name)

if len(files) == 0:
    raise SystemExit("No files for this satellite and period. Nothing to convert.")
print("Converting", len(files), "files")

rows = []
for name in files:
    ds = xr.open_dataset(os.path.join(FOLDER, name))
    if name == files[0]:
        print("Differential flux units:", ds["AvgDiffProtonFlux"].attrs.get("units"))
        print("Integral flux units:", ds["AvgIntProtonFlux"].attrs.get("units"))

    diff = ds["AvgDiffProtonFlux"].values          # (time, sensor, channel)
    diff = np.where(diff > 1e-12, diff, np.nan)
    diff = np.nanmean(diff, axis=1)                 # average east and west sensors
    above_500 = ds["AvgIntProtonFlux"].values       # (time, sensor), >500 MeV
    above_500 = np.nanmean(np.where(above_500 > 1e-12, above_500, np.nan), axis=1)

    if "L2_SciData_TimeStamp" in ds:
        times = pd.to_datetime(ds["L2_SciData_TimeStamp"].values)
    else:
        times = pd.to_datetime(ds["time"].values)

    table = pd.DataFrame({"time_tag": times})
    for e in thresholds:
        # keV of each channel that lies above the threshold e
        width_kev = np.clip(high_mev - np.maximum(low_mev, e), 0, None) * 1000
        table[f"flux_gt{e}MeV"] = np.nansum(diff * width_kev, axis=1) + above_500
    rows.append(table)
    ds.close()

goesr = pd.concat(rows, ignore_index=True).sort_values("time_tag")
out = os.path.join(ROOT, "data", "processed", "GOESR", f"goesr_{SATELLITE}_{START}_{END}.csv")
os.makedirs(os.path.dirname(out), exist_ok=True)
goesr.to_csv(out, index=False)
print(goesr.shape, goesr["time_tag"].min(), "to", goesr["time_tag"].max())
print("Saved", out)
