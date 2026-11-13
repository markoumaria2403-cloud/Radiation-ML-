import io
import time

import pandas as pd
import requests

BASE = "https://visualization.osdr.nasa.gov/radlab/api/"
start = "1990-09-01"
end = "2025-10-01"

months = pd.date_range(start, end, freq="MS")
parts = []

for i in range(len(months) - 1):
    t0 = months[i].strftime("%Y-%m-%dT%H:%M")
    t1 = months[i + 1].strftime("%Y-%m-%dT%H:%M")
    url = (BASE + "?spacecraft=ISS&instrument=DosTel"
           + "&timestamp>=" + t0 + "&timestamp<" + t1
           + "&absorbed_dose_rate&latitude&longitude&altitude&format=csv")
    print("Κατέβασμα", t0, "έως", t1)
    response = requests.get(url, timeout=300)
    response.raise_for_status()
    if response.text.strip():
        parts.append(pd.read_csv(io.StringIO(response.text)))
    time.sleep(2)

data = pd.concat(parts, ignore_index=True)
data.to_csv("iss_dostel_2017-09.csv", index=False)
print(data.shape)
print(data.head())