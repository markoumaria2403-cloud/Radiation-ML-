import pandas as pd
import seaborn as sns
import matplotlib.pyplot as plt
from matplotlib.colors import LogNorm

# ---------------- settings ----------------
FILE = "iss_dostel_2017-09.csv"          # the full 2009-2024 download
EVENT_START = "2017-09-04"               # zoom window around one storm
EVENT_END = "2017-09-16"
INSTRUMENT = "DosTel2"                   # DosTel1 has a gap during Sept 2017

# ---------------- load and clean ----------------
data = pd.read_csv(FILE, usecols=["timestamp", "instrument_id", "absorbed_dose_rate",
                                  "latitude", "longitude", "altitude"])
data["timestamp"] = pd.to_datetime(data["timestamp"])
data = data.drop_duplicates(subset=["timestamp", "instrument_id"])
data = data[data["absorbed_dose_rate"] > 0]

# label each measurement by where the ISS was in its orbit
in_saa = data["latitude"].between(-45, -5) & data["longitude"].between(-80, 0)
high_lat = (data["latitude"].abs() > 45) & ~in_saa
data["region"] = "Rest of orbit"
data.loc[in_saa, "region"] = "South Atlantic Anomaly"
data.loc[high_lat, "region"] = "High latitudes (|lat| > 45)"

region_order = ["Rest of orbit", "South Atlantic Anomaly", "High latitudes (|lat| > 45)"]
region_colors = {"Rest of orbit": "#b9b8b2",
                 "South Atlantic Anomaly": "#eb6834",
                 "High latitudes (|lat| > 45)": "#2a78d6"}

sns.set_theme(style="whitegrid", context="notebook")

# ---------------- plot 1: one storm, every measurement ----------------
event = data[(data["instrument_id"] == INSTRUMENT)
             & (data["timestamp"] >= EVENT_START)
             & (data["timestamp"] < EVENT_END)]

fig, ax = plt.subplots(figsize=(14, 5))
sns.scatterplot(data=event, x="timestamp", y="absorbed_dose_rate", hue="region",
                hue_order=region_order, palette=region_colors, s=6, linewidth=0, ax=ax)
ax.set_yscale("log")
ax.set_title(f"{INSTRUMENT} inside the ISS, {EVENT_START} to {EVENT_END}")
ax.set_xlabel("")
ax.set_ylabel("Absorbed dose rate (µGy/h)")
ax.legend(title="", markerscale=3)
plt.tight_layout()
plt.savefig("plot1_event.png", dpi=150)
plt.show()

# ---------------- plot 2: the whole 2009-2024 series, daily median ----------------
daily = (data[data["region"] == "High latitudes (|lat| > 45)"]
         .set_index("timestamp")
         .groupby("instrument_id")["absorbed_dose_rate"]
         .resample("1D").median()
         .reset_index())

fig, ax = plt.subplots(figsize=(14, 5))
sns.lineplot(data=daily, x="timestamp", y="absorbed_dose_rate", hue="instrument_id",
             palette=["#2a78d6", "#1baf7a"], linewidth=0.8, ax=ax)
ax.set_yscale("log")
ax.set_title("Daily median dose at high latitudes, 2009-2024")
ax.set_xlabel("")
ax.set_ylabel("Absorbed dose rate (µGy/h)")
ax.legend(title="")
plt.tight_layout()
plt.savefig("plot2_daily.png", dpi=150)
plt.show()

# ---------------- plot 3: map of dose along the orbit ----------------
one_instrument = data[data["instrument_id"] == INSTRUMENT]
sample = one_instrument.sample(n=min(200_000, len(one_instrument)), random_state=0)

fig, ax = plt.subplots(figsize=(13, 6))
sns.scatterplot(data=sample, x="longitude", y="latitude", hue="absorbed_dose_rate",
                hue_norm=LogNorm(), palette="rocket_r", s=3, linewidth=0, ax=ax)
ax.set_title(f"{INSTRUMENT}: where along the orbit the dose is high")
ax.set_xlabel("Longitude (degrees)")
ax.set_ylabel("Latitude (degrees)")
ax.legend(title="µGy/h", markerscale=4, loc="lower left")
plt.tight_layout()
plt.savefig("plot3_map.png", dpi=150)
plt.show()

# ---------------- plot 4: dose distribution per orbit region ----------------
fig, ax = plt.subplots(figsize=(10, 5))
sns.boxplot(data=one_instrument, x="region", y="absorbed_dose_rate",
            order=region_order, hue="region", palette=region_colors, legend=False,
            showfliers=False, ax=ax)
ax.set_yscale("log")
ax.set_title(f"{INSTRUMENT}: dose by orbit region, 2009-2024")
ax.set_xlabel("")
ax.set_ylabel("Absorbed dose rate (µGy/h)")
plt.tight_layout()
plt.savefig("plot4_regions.png", dpi=150)
plt.show()
