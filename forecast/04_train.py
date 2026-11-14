import os
import pickle

import matplotlib
matplotlib.use("Agg")                      
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns
from sklearn.linear_model import LogisticRegression, Ridge
from sklearn.metrics import (brier_score_loss, f1_score, mean_squared_error,
                             r2_score, roc_auc_score)
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from features import FEATURES        

ROOT = os.path.dirname(os.path.abspath(__file__))   
TABLE = os.path.join(ROOT, "data", "processed", "snapshot_table.csv")
MODEL_FILE = os.path.join(ROOT, "models", "forecast_models.pkl")
RESULTS_FILE = os.path.join(ROOT, "data", "processed", "results.csv")
FIGURES = os.path.join(ROOT, "Figures", "training")


SIZE_TARGETS = ["log_peak", "log_fluence_10_30", "log_fluence_30_50",
                "log_fluence_50_100", "log_fluence_100"]
# when (yes = 1 / no = 0)
TIME_TARGETS = ["peak_passed", "peak_within_6h"]

SEVERE = np.log10(100)          # 100 pfu = NOAA level S2, used for the F1 score

os.makedirs(os.path.dirname(MODEL_FILE), exist_ok=True)
os.makedirs(FIGURES, exist_ok=True)



#LOAD THE TABLE
table = pd.read_csv(TABLE).dropna(subset=FEATURES)
table["peak_passed"] = (table["hours_to_peak"] == 0).astype(int)
table["peak_within_6h"] = (table["hours_to_peak"] <= 6).astype(int)
cycles = sorted(table["cycle"].unique())
print("Storms:", table["event"].nunique(), "| rows:", len(table), "| solar cycles:", cycles)


# TEST: train on 3 solar cycles, predict the 4th, repeat for each cycle

predictions = []
for test_cycle in cycles:
    train = table[table["cycle"] != test_cycle]
    test = table[table["cycle"] == test_cycle]

    for target in SIZE_TARGETS + TIME_TARGETS:
        # baseline 
        if target in SIZE_TARGETS:
            typical = train.groupby("hours_since_onset")[target].median()
            model = make_pipeline(StandardScaler(), Ridge(alpha=1.0))
            model.fit(train[FEATURES], train[target])
            predicted = model.predict(test[FEATURES])
        else:
            typical = train.groupby("hours_since_onset")[target].mean()
            model = make_pipeline(StandardScaler(), LogisticRegression(C=0.3, max_iter=1000))
            model.fit(train[FEATURES], train[target])
            predicted = model.predict_proba(test[FEATURES])[:, 1]

        predictions.append(pd.DataFrame({
            "target": target,
            "cycle": test_cycle,
            "event": test["event"].values,
            "hours_since_onset": test["hours_since_onset"].values,
            "observed": test[target].values,
            "model": predicted,
            "baseline": test["hours_since_onset"].map(typical).values,
        }))

predictions = pd.concat(predictions, ignore_index=True)


# SCORES, per target and per hour since onset
rows = []
for (target, hour), g in predictions.groupby(["target", "hours_since_onset"]):
    row = {"target": target, "hours_since_onset": hour, "n": len(g)}
    if target in SIZE_TARGETS:
        row["R2"] = r2_score(g["observed"], g["model"])
        row["RMSE"] = np.sqrt(mean_squared_error(g["observed"], g["model"]))
        row["within_x2_pct"] = 100 * np.mean(np.abs(g["model"] - g["observed"]) < np.log10(2))
        row["baseline_within_x2_pct"] = 100 * np.mean(np.abs(g["baseline"] - g["observed"]) < np.log10(2))
        if target == "log_peak":
            row["F1_100pfu"] = f1_score(g["observed"] >= SEVERE, g["model"] >= SEVERE)
    else:
        row["AUC"] = roc_auc_score(g["observed"], g["model"])
        # 0 = no better than the baseline, 1 = perfect
        row["Brier_skill"] = 1 - (brier_score_loss(g["observed"], g["model"])
                                  / brier_score_loss(g["observed"], g["baseline"]))
    rows.append(row)

results = pd.DataFrame(rows)
results.to_csv(RESULTS_FILE, index=False)

pd.set_option("display.width", 160)
size = results[results["target"].isin(SIZE_TARGETS)]
time = results[results["target"].isin(TIME_TARGETS)]
print("\n--- HOW BIG: R2 (1 = perfect, 0 = no better than the typical value) ---")
print(size.pivot(index="target", columns="hours_since_onset", values="R2").round(2))
print("\n--- HOW BIG: % of forecasts within a factor of 2 (model / baseline) ---")
print(size.pivot(index="target", columns="hours_since_onset", values="within_x2_pct").round(0))
print(size.pivot(index="target", columns="hours_since_onset", values="baseline_within_x2_pct").round(0))
print("\n--- HOW BIG: F1 of the warning 'peak will reach 100 pfu' ---")
print(size[size["target"] == "log_peak"].set_index("hours_since_onset")["F1_100pfu"].round(2))
print("\n--- WHEN: AUC (0.5 = guessing, 1 = perfect) ---")
print(time.pivot(index="target", columns="hours_since_onset", values="AUC").round(2))
print("\n--- WHEN: Brier skill (0 = no better than the baseline) ---")
print(time.pivot(index="target", columns="hours_since_onset", values="Brier_skill").round(2))


# FINAL MODELS: trained on ALL storms, saved in one file
ranges = table[FEATURES].agg(["min", "max"])
saved = {"features": FEATURES, "ranges": ranges, "size": {}, "time": {}}
for target in SIZE_TARGETS:
    model = make_pipeline(StandardScaler(), Ridge(alpha=1.0))
    saved["size"][target] = model.fit(table[FEATURES], table[target])
for target in TIME_TARGETS:
    model = make_pipeline(StandardScaler(), LogisticRegression(C=0.3, max_iter=1000))
    saved["time"][target] = model.fit(table[FEATURES], table[target])

with open(MODEL_FILE, "wb") as f:
    pickle.dump(saved, f)
print("\nModels saved in", MODEL_FILE)


# FIGURES
sns.set_theme(style="whitegrid")

# 6a. predicted vs observed, 1 hour after onset
one_hour = predictions[predictions["hours_since_onset"] == 1]
fig, axes = plt.subplots(1, 2, figsize=(12, 5))
for ax, target, title in [(axes[0], "log_peak", "Peak flux >10 MeV"),
                          (axes[1], "log_fluence_100", "Fluence >100 MeV")]:
    d = one_hour[one_hour["target"] == target]
    sns.scatterplot(data=d, x="observed", y="model", hue="cycle", s=25, ax=ax)
    low, high = d[["observed", "model"]].min().min(), d[["observed", "model"]].max().max()
    ax.plot([low, high], [low, high], "k--", lw=1)
    ax.fill_between([low, high], [low - np.log10(2), high - np.log10(2)],
                    [low + np.log10(2), high + np.log10(2)], color="grey", alpha=0.15)
    ax.set_title(title + ", 1 hour after onset (grey = within x2)")
    ax.set_xlabel("observed (log10)")
    ax.set_ylabel("predicted (log10)")
fig.tight_layout()
fig.savefig(os.path.join(FIGURES, "predicted_vs_observed.png"), dpi=150)
plt.close(fig)

# 6b. how the skill grows with time since onset
fig, axes = plt.subplots(1, 2, figsize=(12, 5))
sns.lineplot(data=size, x="hours_since_onset", y="R2", hue="target", marker="o", ax=axes[0])
axes[0].set_title("How big: R2")
sns.lineplot(data=time, x="hours_since_onset", y="AUC", hue="target", marker="o", ax=axes[1])
axes[1].axhline(0.5, color="k", ls="--", lw=1)
axes[1].set_title("When: AUC (0.5 = guessing)")
fig.tight_layout()
fig.savefig(os.path.join(FIGURES, "skill_by_hour.png"), dpi=150)
plt.close(fig)

print("Figures saved in", FIGURES)
