import pandas as pd
from sklearn.preprocessing import LabelEncoder
from sklearn.model_selection import train_test_split
from sklearn.ensemble import RandomForestRegressor
import joblib

df = pd.read_csv("synthetic_health_lifestyle_dataset.csv")

df['Exercise_Freq'] = df['Exercise_Freq'].fillna('Unknown')
df['Alcohol_Consumption'] = df['Alcohol_Consumption'].fillna('Unknown')

cat_cols = ['Gender', 'Smoker', 'Exercise_Freq', 'Diet_Quality', 'Alcohol_Consumption', 'Chronic_Disease']
le_dict = {}
for col in cat_cols:
    le = LabelEncoder()
    df[col] = le.fit_transform(df[col])
    le_dict[col] = le

activity_map = {'Unknown': 'Low', 'Rarely': 'Low', 'Sometimes': 'Moderate', 'Often': 'High'}
df['Activity_Level'] = df['Exercise_Freq'].map(activity_map)

def water_intake(row):
    base = row['Weight_kg'] * 0.035
    activity_multiplier = {'Low': 1.0, 'Moderate': 1.2, 'High': 1.4}
    act = activity_multiplier.get(row['Activity_Level'], 1.0)
    return base * act

def calories_intake(row):
    if row['Gender'] == 0:
        bmr = 10*row['Weight_kg'] + 6.25*row['Height_cm'] - 5*row['Age'] - 161
    elif row['Gender'] == 1:
        bmr = 10*row['Weight_kg'] + 6.25*row['Height_cm'] - 5*row['Age'] + 5
    else:
        bmr = 10*row['Weight_kg'] + 6.25*row['Height_cm'] - 5*row['Age'] - 78
    activity_factor = {'Low': 1.2, 'Moderate': 1.55, 'High': 1.725}
    return bmr * activity_factor.get(row['Activity_Level'], 1.2)

def adjusted_calories(row):
    bmr = 10 * row['Weight_kg'] + 6.25 * row['Height_cm'] - 5 * row['Age'] - 161
    activity_factor = 1.55
    return bmr * activity_factor

def adjusted_water_intake(row):
    base_intake = row['Weight_kg'] * 0.035
    activity_multiplier = 1.2
    return base_intake * activity_multiplier

df['Water_Liters'] = df.apply(water_intake, axis=1)
df['Calories'] = df.apply(calories_intake, axis=1)
df.to_csv("preprocessed_health_lifestyle_dataset.csv", index=False)

features = ['Age','Gender','Height_cm','Weight_kg','BMI','Smoker','Exercise_Freq',
            'Diet_Quality','Alcohol_Consumption','Chronic_Disease','Stress_Level','Sleep_Hours']

X = df[features]
y_calories = df['Calories']
y_water = df['Water_Liters']

X_train_cal, X_test_cal, y_train_cal, y_test_cal = train_test_split(X, y_calories, test_size=0.2, random_state=42)
X_train_w, X_test_w, y_train_w, y_test_w = train_test_split(X, y_water, test_size=0.2, random_state=42)

model_cal = RandomForestRegressor(n_estimators=100, random_state=42)
model_cal.fit(X_train_cal, y_train_cal)

model_water = RandomForestRegressor(n_estimators=100, random_state=42)
model_water.fit(X_train_w, y_train_w)

joblib.dump(model_cal, "model_calories.pkl")
joblib.dump(model_water, "model_water.pkl")
joblib.dump(le_dict, "label_encoders.pkl")

def suggest_plan(weight, height, calories, water):
    bmi = weight / (height/100)**2
    suggestion = ""
    if bmi < 18.5:
        suggestion += "You are underweight. Consider a calorie-rich balanced diet.\n"
    elif 18.5 <= bmi < 24.9:
        suggestion += "Your weight is normal. Maintain your healthy lifestyle.\n"
    elif 25 <= bmi < 29.9:
        suggestion += "You are overweight. Focus on balanced diet and moderate exercise.\n"
    else:
        suggestion += "You are obese. Follow a controlled diet and regular exercise.\n"
    
    if water < 2.5:
        suggestion += "Increase your daily water intake to stay hydrated.\n"
    else:
        suggestion += "Your water intake is sufficient.\n"
    
    return suggestion
