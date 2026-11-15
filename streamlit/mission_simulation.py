# =====================================================================
# mission_simulation.py  -  the 14-day mission, hour by hour, for our Streamlit app
#
#   6 astronauts, 14 days, the REAL solar storm of 11 November 2025 (GOES-19)
#   a slider moves through the mission: rooms coloured by their dosimeter, every astronaut where he was
#   below: the dose of one astronaut with the warning (shelter) and without it
#
# Reads (warning/simulate_room_sensors.py + warning/crew_routes.py):
#   shielding/cad/orion_floor_plans.gpkg, warning/data/crew_log.csv,
#   warning/data/room_sensors_log.csv, warning/data/crew_routes_readable.json
#
# Run alone:  streamlit run mission_simulation.py      (or copy the block into our app)
# =====================================================================
import json
import os

import geopandas as gpd
import pandas as pd
import plotly.graph_objects as go
import pyogrio
import streamlit as st

# DATA = the folder with the data (the copies next to this file, or the project folder)
DATA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
FLOOR_PLANS = os.path.join(DATA, "shielding", "cad", "orion_floor_plans.gpkg")
CREW_LOG = os.path.join(DATA, "warning", "data", "crew_log.csv")
SENSORS = os.path.join(DATA, "warning", "data", "room_sensors_log.csv")
READABLE = os.path.join(DATA, "warning", "data", "crew_routes_readable.json")
FLOOR_GAP = 6.0

st.title("🎬 14 days, 6 astronauts, one real solar storm")

# --- the story in one paragraph ---
readable = json.load(open(READABLE, encoding="utf-8"))
st.success(f"### {readable['headline']}")
for line in readable["why"]:
    st.markdown("- " + line)


log = pd.read_csv(CREW_LOG, parse_dates=["time"])
sensors = pd.read_csv(SENSORS, parse_dates=["time"]).pivot_table(index="time", columns="room", values="dose_rate_msv_h")
plans = pd.concat([gpd.read_file(FLOOR_PLANS, layer=layer) for layer in pyogrio.list_layers(FLOOR_PLANS)[:, 0]])
plans = plans[plans["floor"] >= 2]                           # the crew floors

# --- the slider: one hour of the mission ---
hours = sorted(log["time"].dt.floor("h").unique())
storm = log.loc[log["room"] == "shelter", "time"].min()
pick = st.select_slider("Move through the mission", options=hours,
                        value=storm.floor("h") if pd.notna(storm) else hours[0],
                        format_func=lambda t: pd.Timestamp(t).strftime("%d %b, %H:%M"))
at = log[log["time"] == pick]
rate = sensors.loc[pick]

fig = go.Figure()
for _, r in plans.iterrows():
    shift = FLOOR_GAP * (r["floor"] - 2)
    x, y = r.geometry.exterior.xy
    value = rate.get(r["room_key"], 0) if r["type"] == "room" else 0
    color = "#8a949e" if r["type"] == "hull" else "#d5d9dd" if r["type"] == "equipment" else \
        "#2e9e5b" if value < 0.05 else "#f0a33a" if value < 0.3 else "#d64541"
    fig.add_trace(go.Scatter(x=[a + shift for a in x], y=list(y), fill="toself", fillcolor=color, mode="lines",
                             line={"color": "#33404d", "width": 0.6}, hoverinfo="text", showlegend=False,
                             text=f"{r['name']}: {value:.2f} mSv/h" if r["type"] == "room" else r["name"]))
for floor in [2, 3, 4]:
    fig.add_annotation(x=FLOOR_GAP * (floor - 2), y=2.9, text=f"<b>Floor {floor}</b>", showarrow=False)
fig.add_trace(go.Scatter(x=at["x"] + FLOOR_GAP * (at["floor"] - 2), y=at["y"], mode="markers+text",
                         text=at["astronaut"], textposition="top center", showlegend=False,
                         marker={"size": 14, "color": "#14213d", "line": {"color": "white", "width": 2}}))
fig.update_layout(height=400, margin={"l": 0, "r": 0, "t": 10, "b": 0}, plot_bgcolor="white")
fig.update_xaxes(visible=False)
fig.update_yaxes(visible=False, scaleanchor="x")
st.plotly_chart(fig, use_container_width=True)
st.caption("Green = quiet · orange = storm · red = strong storm in that room (what its dosimeter reads)")

# --- the dose of one astronaut, with and without the warning ---
dose = log.groupby("time")[["dose_msv", "dose_if_no_warning_msv"]].mean()
fig = go.Figure()
fig.add_trace(go.Scatter(x=dose.index, y=dose["dose_if_no_warning_msv"], name="without the warning",
                         line={"color": "#d64541", "dash": "dash"}))
fig.add_trace(go.Scatter(x=dose.index, y=dose["dose_msv"], name="with the warning (shelter)",
                         line={"color": "#2e9e5b", "width": 3}))
fig.add_vline(x=pick, line_color="#14213d")
fig.update_layout(height=300, yaxis_title="dose of one astronaut (mSv)", margin={"l": 0, "r": 0, "t": 10, "b": 0},
                  legend={"orientation": "h"})
st.plotly_chart(fig, use_container_width=True)
