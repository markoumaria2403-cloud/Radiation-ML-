# Storm Forecast Module: ML forecasting of Solar Energetic Particle (SEP) events

Part of the **Dynamic Shielding Map** project for the NASA Space Apps Challenge.

When a solar proton storm starts, the astronaut needs two answers: **how bad will it get** and
**how much time is left**. This module answers both from the proton flux measured in the first
hours of the storm. The `warning/` module turns it into an alert and the `shielding/` module converts the forecast into a dose for each room of
the Orion spacecraft.

---

## What it predicts

At any moment from **30 minutes to 6 hours after a storm starts** (a storm starts when the >10 MeV
flux goes above 10 pfu, the NOAA S1 level):

| Question | Target | Model |
|---|---|---|
| How big? | peak flux >10 MeV (`log_peak`) | Ridge regression |
| How much radiation, per energy band? | fluence 10-30, 30-50, 50-100 and >100 MeV | Ridge regression |
| When? | probability that the peak has **already passed** | Logistic regression |
| When? | probability that the peak comes **within the next 6 h** | Logistic regression |

The fluence per energy band feeds the shielding calculation: a room with a given wall thickness
(g/cm²) stops protons below a certain energy, so each band hits each room differently.

## Data

| Source | Period | Storms |
|---|---|---|
| **GSEP** catalog (Rotti et al. 2022), built from the older NOAA GOES satellites | 1986-2017 | ~244 |
| **NOAA GOES-R SGPS** (GOES-16, GOES-19), 5-minute averages, storms found by `02_detect_events.py` | 2020-2026 | 57 |

Total: **301 storms** across 4 solar cycles (SC22-SC25).

The GOES-R instruments read a higher flux than the old GOES when the Sun is quiet, so each
GOES-R channel is shifted so its quiet level matches GSEP's.

## Features (computed only from data up to "now")

`features.py` holds the single function that computes them, used by both training and prediction.

| Feature | Meaning |
|---|---|
| `hours_since_onset` | time since the storm started |
| `log_p10_now`, `log_p30_now`, `log_p50_now`, `log_p100_now` | current flux above 10 / 30 / 50 / 100 MeV |
| `rise_per_hour` | how fast the >10 MeV flux is rising (last 30 min) |
| `hardness` | log(flux >100 / flux >10): how many high-energy protons |
| `log_max_so_far` | highest >10 MeV flux since onset |
| `below_max_so_far` | how far the flux has dropped from that maximum |
| `log_background` | median flux in the 12 h before onset |

## Results

Leave-one-solar-cycle-out validation: trained on 3 cycles, tested on the 4th, for each of the 4 cycles.

| Hours after onset | 0.5 | 1 | 2 | 4 | 6 |
|---|---|---|---|---|---|
| R², fluence >100 MeV | 0.65 | 0.73 | 0.79 | 0.85 | 0.87 |
| R², peak flux | 0.33 | 0.45 | 0.58 | 0.68 | 0.72 |

- Warning "the storm will reach 100 pfu": F1 0.63-0.84
- "Peak already passed": AUC 0.76-0.86
- "Peak within 6 h": better than the baseline only from 4 h after onset, so it is hidden before that.
- XGBoost and LightGBM were tested and did not beat Ridge (about 300 storms is too few for them).

**Limits:** extreme storms beyond the training range are underpredicted (e.g. the S4 storm of
January 2026). `05_predict.py` flags forecasts that use feature values never seen in training
(`outside_training` column).

---

## Folder structure

```
forecast/                  everything of this module is inside this folder
  README.md
  features.py              shared feature code (imported by 03, 05 and live/06_live.py)
  01_download_goesr.py     download GOES-R proton data from NOAA
  02_detect_events.py      match quiet levels to GSEP, find storms in GOES-R
  03_build_table.py        one row per storm per snapshot time (0.5, 1, 2, 4, 6 h)
  04_train.py              validate and train the models
  05_predict.py            forecast on any proton-flux data
  data/raw/                GSEP_List.csv, gsep/ (storm files), goesr/, goesr_events/, GOESR_List.csv
  data/processed/          GOES-R series, snapshot_table.csv, results.csv, forecast_output.csv
  models/                  forecast_models.pkl (made by 04)
  Figures/                 training/ (04) and forecasts/ (05)
```

`data/`, `models/` and the forecast figures are not in git: they are large or re-made by the scripts.

## How to run

Requirements: Python 3.10+ and

```
pip install pandas numpy scikit-learn matplotlib seaborn xarray netCDF4
```

(`xarray` and `netCDF4` are needed only by `01_download_goesr.py`.)

**Training (once, or when new data are added):**

```
python forecast/01_download_goesr.py    # set SATELLITE, START, END at the top; run once per satellite
python forecast/02_detect_events.py
python forecast/03_build_table.py
python forecast/04_train.py
```

The GSEP catalog and its storm files must be in `forecast/data/raw/` (download them from the GSEP data
release, Rotti et al. 2022).

**Forecast:**

```
python forecast/05_predict.py
```

Output: `forecast/data/processed/forecast_output.csv` (one row every 15 minutes per storm) and one figure
per storm in `forecast/Figures/forecasts/`.

## Live forecast

The live version (every 5 minutes, from NOAA real-time data) is in the `live/` folder:
`python live/06_live.py`. See `live/README.md`.

## Using your own data

`05_predict.py` works on any CSV with a time column and the integral proton flux (pfu) above
10, 30, 50 and 100 MeV. Change only section 1 (SETTINGS):

```python
INPUT_FILE = "my_flux.csv"
TIME_COLUMN = "time"
CHANNELS = {"my_10MeV_column": "p10", "my_30MeV_column": "p30",
            "my_50MeV_column": "p50", "my_100MeV_column": "p100"}
START, END = None, None
QUIET = {"p10": ..., "p30": ..., "p50": ..., "p100": ...}   # quiet-Sun level of your instrument
```

`QUIET` is the flux your instrument reads when the Sun is quiet (for example the 10th percentile
of each channel over a quiet month). Use `None` for data from the old GOES or GSEP. The values
for GOES-16 and GOES-19 are given in the script.

## Credits

- Proton data: NOAA GOES-R SGPS (NOAA NCEI).
- Storm catalog: GSEP, Rotti et al. (2022), *The Astrophysical Journal Supplement Series*.
