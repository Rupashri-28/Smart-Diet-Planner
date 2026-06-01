import pandas as pd

df = pd.read_csv("synthetic_health_lifestyle_dataset.csv")

print(df.head())
print(df.info())
print(df.isnull().sum())
