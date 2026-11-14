# Warning

Turns the live forecast (`live/06_live.py`) into one alert level for the astronaut.

(work in progress)

- alert level from the measured flux (NOAA S-scale), independent of the model
- worst case of the forecast (forecast + 1.65 x RMSE)
- warning when the measured flux goes above the forecast
- final level = the higher of the two, with one clear message: ALL CLEAR / WATCH / GO TO SHELTER
