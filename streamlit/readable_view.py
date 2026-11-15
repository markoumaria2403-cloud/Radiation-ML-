# =====================================================================
# readable_view.py  -  the plain-words results of every algorithm, ready for our app
#
# Every algorithm writes a "..._readable.json" with the SAME shape:
#   level        green / yellow / red
#   headline     one sentence
#   what_to_do   what the astronaut must do
#   why          the reasons, in words
#   crew         one message per astronaut (health: status, radiation, body, early_sign)
#
# Copy this block into our Streamlit app (or run it alone: streamlit run app/readable_view.py)
# =====================================================================
import json
import os

import streamlit as st

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")   # or the project folder for live data
FILES = {"🚨 Alert": os.path.join(ROOT, "warning", "data", "alert_readable.json"),
         "🧭 Where to go": os.path.join(ROOT, "shielding", "data", "shielding_readable.json"),
         "❤️ Health": os.path.join(ROOT, "health", "data", "health_readable.json"),
         "🎬 The 14-day mission": os.path.join(ROOT, "warning", "data", "crew_routes_readable.json")}
BOX = {"green": st.success, "yellow": st.warning, "red": st.error}
ICON = {"green": "✅", "yellow": "⚠️", "red": "🛑"}

for title, path in FILES.items():
    if not os.path.exists(path):
        continue
    r = json.load(open(path))
    st.subheader(title)
    BOX[r["level"]](f"**{r['headline']}**  \n{r['what_to_do']}")
    for line in r["why"]:
        st.markdown("- " + line)
    columns = st.columns(3)
    for i, (astronaut, c) in enumerate(r.get("crew", {}).items()):
        with columns[i % 3].container(border=True):
            st.markdown(f"**{ICON[c['level']]} {astronaut}**")
            if "message" in c:                                   # alert, where to go, mission
                st.write(c["message"])
            else:                                                # health card
                st.markdown(f"**{c['status']}**")
                st.caption("☢️ " + c["radiation"])
                for b in c["body"]:
                    st.write("🌡️ " + b)
                if c["early_sign"]:
                    st.write("🔎 " + c["early_sign"])
