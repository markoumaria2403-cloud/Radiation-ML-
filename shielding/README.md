# Shielding

Converts the forecast fluence per energy band (from `forecast/`) into a dose for each room of the
Orion spacecraft and picks the safest room.

(work in progress)

## Destel/

Dose measured inside the International Space Station by the DOSTEL dosimeter (NASA OSDR RadLab),
used as a reference for a real dose behind spacecraft walls, e.g. during the September 2017 storm.

- `dostel.py`: downloads the data (`iss_dostel_2017-09.csv`, large, not in git)
- `plot_dostel.py`: the figures `plot1_event.png` ... `plot4_regions.png`
- `dostel_2017-09-01_20.csv`: small extract
