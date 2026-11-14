import os

import pandas as pd
import matplotlib.pyplot as plt

# project folder = one level above this script, so it runs from anywhere
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

df = pd.read_csv(os.path.join(ROOT, "iss_dostel_2017-09.csv"))

print(df.columns)
