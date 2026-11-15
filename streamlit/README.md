# For our Streamlit app

Copies of everything our app needs to show the floor plans, the simulation and the results in plain words.

| File | What it shows |
|---|---|
| `floor_plan_live.py` | the 3 crew floors of Orion: rooms coloured Safe / Low risk / Caution / Avoid (worst-case dose of the storm), every astronaut where he is, his route when he must move; on top the one sentence and a card per astronaut |
| `mission_simulation.py` | the 14-day mission with the real storm of 11 November 2025: a slider hour by hour (rooms coloured by their dosimeter, astronauts where they were) and the dose with / without the warning |
| `readable_view.py` | the results of every algorithm in plain words: alert, where to go, health, the 14-day mission |
| `data/` | copies of the data they read, in the same folders as in the project |

Each file runs alone (`streamlit run floor_plan_live.py`) or can be copied into a page of our app
(e.g. into the `pages/` folder of a multipage Streamlit app). No functions, no `st.set_page_config`,
so they fit inside our app.

**Live data**: in each file change one line, `DATA = ...`, to the project folder
(e.g. `DATA = r"C:\Creations\python\hackathlon\Radiation-ML-"`). Then the floor plans follow
`live/06_live.py` every 5 minutes (the "Refresh every 5 seconds" switch keeps the page up to date).

Needs: `pip install streamlit plotly geopandas pyogrio pandas`
