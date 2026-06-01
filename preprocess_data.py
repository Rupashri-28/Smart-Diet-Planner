import pandas as pd
from sklearn.preprocessing import LabelEncoder
from sklearn.model_selection import train_test_split

df = pd.read_csv("synthetic_health_lifestyle_dataset.csv")

df['Exercise_Freq'] = df['Exercise_Freq'].fillna('Unknown')
df['Alcohol_Consumption'] = df['Alcohol_Consumption'].fillna('Unknown')

cat_cols = ['Gender', 'Smoker', 'Exercise_Freq', 'Diet_Quality', 'Alcohol_Consumption', 'Chronic_Disease']
le_dict = {}
for col in cat_cols:
    le = LabelEncoder()
    df[col] = le.fit_transform(df[col])
    le_dict[col] = le

df['Water_Liters'] = df['Weight_kg'] * 0.035

X = df[['Age','Gender','Height_cm','Weight_kg','BMI','Smoker','Exercise_Freq',
        'Diet_Quality','Alcohol_Consumption','Chronic_Disease','Stress_Level','Sleep_Hours']]

y_calories = df['Calories'] if 'Calories' in df.columns else None
y_water = df['Water_Liters']

X_train_cal, X_test_cal, y_train_cal, y_test_cal = train_test_split(X, y_calories, test_size=0.2, random_state=42) if y_calories is not None else (None,None,None,None)
X_train_w, X_test_w, y_train_w, y_test_w = train_test_split(X, y_water, test_size=0.2, random_state=42)

df.to_csv("preprocessed_health_lifestyle_dataset.csv", index=False)
