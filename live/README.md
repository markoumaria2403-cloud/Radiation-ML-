# Live

The program that runs in the app. It runs non-stop and every 5 minutes reads the newest proton flux,
checks for a solar proton storm and, if there is one, runs the models of `forecast/`.

```
python live/06_live.py        # stop with Ctrl+C
```

It uses `forecast/features.py` and `forecast/models/forecast_models.pkl`, so run
`forecast/03_build_table.py` and `forecast/04_train.py` first.

| Situation | What it does |
|---|---|
| no storm (>10 MeV flux below 10 pfu) | `ALL CLEAR` |
| storm, first 30 minutes | `STORM STARTED`, first forecast at onset + 30 min |
| storm, 30 min to 6 h | a new forecast every 5 minutes |
| storm, after 6 h | keeps the forecast made at 6 h (the models were trained up to 6 h) |

- `MODE = "live"`: the last 7 days of GOES proton flux from NOAA's Space Weather Prediction Center
  (`services.swpc.noaa.gov`). The instrument's quiet level is measured automatically
  (10th percentile of the last 7 days), so it works whichever GOES satellite NOAA uses as primary.
- `MODE = "replay"`: plays an old storm from a file as if it were happening now (default: the S4 storm
  of January 2026, 5 minutes of data every 0.5 s), for testing and for the demo.

Output: `live/data/live_log.csv` (one row every 5 minutes) and `live/Figures/live.png`
(redrawn every 5 minutes).

## Next

The `warning/` and `shielding/` steps will be added to this loop: forecast -> alert level -> safest room.
