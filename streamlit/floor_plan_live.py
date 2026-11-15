# =====================================================================
# floor_plan_live.py  -  the floor plans of Orion, live, for our Streamlit app
#
#   rooms coloured by the worst-case dose of the storm (Safe / Low risk / Caution / Avoid)
#   every astronaut where he is now, and his route when he must move
#   on top: the one sentence of shielding.py, and a card per astronaut
#
# Reads (written every 5 minutes by live/06_live.py -> shielding/shielding.py):
#   shielding/cad/orion_floor_plans.gpkg, shielding/data/room_doses.json,
#   shielding/data/crew_orders.json, shielding/data/shielding_readable.json
#
# Run alone:  streamlit run floor_plan_live.py      (or copy the block into our app)
# =====================================================================
import json
import os
import time

import geopandas as gpd
import pandas as pd
import plotly.graph_objects as go
import pyogrio
import streamlit as st

# DATA = the folder with the data. Here: the copies next to this file.
# For LIVE data: the project folder, e.g. DATA = r"C:\Creations\python\hackathlon\Radiation-ML-"
DATA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
FLOOR_PLANS = os.path.join(DATA, "shielding", "cad", "orion_floor_plans.gpkg")
ROOM_DOSES = os.path.join(DATA, "shielding", "data", "room_doses.json")
CREW_ORDERS = os.path.join(DATA, "shielding", "data", "crew_orders.json")
READABLE = os.path.join(DATA, "shielding", "data", "shielding_readable.json")

FLOOR_GAP = 6.0              # metres between the floor plans
LEVEL_COLORS = {"SAFE": "#2e9e5b", "LOW": "#a3c94f", "MEDIUM": "#f0a33a", "HIGH": "#d64541"}
LEVEL_WORDS = {"SAFE": "Safe", "LOW": "Low risk", "MEDIUM": "Caution", "HIGH": "Avoid"}
BOX = {"green": st.success, "yellow": st.warning, "red": st.error}
ICON = {"green": "✅", "yellow": "⚠️", "red": "🛑"}

st.title("🛰️ Orion: where everyone is")
auto = st.toggle("Refresh every 5 seconds", value=False)

# --- the one sentence and the cards ---
readable = json.load(open(READABLE, encoding="utf-8"))
BOX[readable["level"]](f"### {readable['headline']}\n{readable['what_to_do']}")
for line in readable["why"]:
    st.markdown("- " + line)
columns = st.columns(3)
for i, (astronaut, c) in enumerate(readable["crew"].items()):
    with columns[i % 3].container(border=True):
        st.markdown(f"**{ICON[c['level']]} {astronaut}**")
        st.write(c["message"])

# --- the floor plans ---
plans = pd.concat([gpd.read_file(FLOOR_PLANS, layer=layer) for layer in pyogrio.list_layers(FLOOR_PLANS)[:, 0]])
plans = plans[plans["floor"] >= 2]                           # the crew floors
rooms = pd.DataFrame(json.load(open(ROOM_DOSES))["rooms"]).T
orders = pd.DataFrame(json.load(open(CREW_ORDERS))["orders"])
moving = orders[orders["route"] != ""]

fig = go.Figure()
for _, r in plans.iterrows():
    shift = FLOOR_GAP * (r["floor"] - 2)
    x, y = r.geometry.exterior.xy
    level = rooms["level"].get(r["room_key"]) if r["type"] == "room" else None
    color = "#8a949e" if r["type"] == "hull" else "#d5d9dd" if r["type"] == "equipment" else LEVEL_COLORS.get(level, "#eef1f4")
    hover = f"{r['name']}: {LEVEL_WORDS.get(level, '')}" if r["type"] == "room" else r["name"]
    fig.add_trace(go.Scatter(x=[a + shift for a in x], y=list(y), fill="toself", fillcolor=color, mode="lines",
                             line={"color": "#33404d", "width": 0.6}, hoverinfo="text", text=hover, showlegend=False))
    if r["type"] == "room":
        c = r.geometry.representative_point()
        fig.add_annotation(x=c.x + shift, y=c.y, text=r["name"], showarrow=False, font={"size": 9})
for floor in [2, 3, 4]:
    fig.add_annotation(x=FLOOR_GAP * (floor - 2), y=2.9, text=f"<b>Floor {floor}</b>", showarrow=False)

centre = plans[plans["type"] == "room"].set_index("room_key").geometry.representative_point()
floor_of = plans[plans["type"] == "room"].set_index("room_key")["floor"]
for _, o in moving.iterrows():
    path = o["route"].split(" -> ")
    fig.add_trace(go.Scatter(x=[centre[p].x + FLOOR_GAP * (floor_of[p] - 2) for p in path],
                             y=[centre[p].y for p in path], mode="lines", hoverinfo="skip", showlegend=False,
                             line={"color": "#1f5fbf", "width": 3, "dash": "dot"}))
fig.add_trace(go.Scatter(x=orders["x"] + FLOOR_GAP * (orders["floor"] - 2), y=orders["y"], mode="markers+text",
                         text=orders["astronaut"], textposition="top center", hoverinfo="text", showlegend=False,
                         marker={"size": 14, "color": "#14213d", "line": {"color": "white", "width": 2}}))
for level, color in LEVEL_COLORS.items():                    # legend
    fig.add_trace(go.Scatter(x=[None], y=[None], mode="markers", name=LEVEL_WORDS[level],
                             marker={"size": 12, "color": color, "symbol": "square"}))
fig.update_layout(height=450, margin={"l": 0, "r": 0, "t": 10, "b": 0}, plot_bgcolor="white",
                  legend={"orientation": "h", "y": -0.05})
fig.update_xaxes(visible=False)
fig.update_yaxes(visible=False, scaleanchor="x")
st.plotly_chart(fig, use_container_width=True)
st.caption("Room colours = the dose a person would get there in the worst case of this storm. "
           "Blue dotted line = the route to the safe room.")

if auto:
    time.sleep(5)
    st.rerun()
