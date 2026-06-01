import streamlit as st
import pandas as pd
import joblib
import random
import time
import threading
import platform
from datetime import datetime
from plyer import notification
import google.generativeai as genai
import plotly.graph_objects as go

# ---------------------- Config & Styling ----------------------
st.set_page_config(page_title="Smart Diet Planner", layout="wide")
st.markdown("<style>body {scroll-behavior: smooth;}</style>", unsafe_allow_html=True)

# Keep your custom styles (slightly cleaned)
st.markdown("""
<style>
.block-container {padding-top: 1rem; padding-bottom: 1rem; max-width: 1200px !important; width: 100%; margin-left: auto; margin-right: auto;}
.stButton>button {background-color: #4F8EF7; color: white; border-radius: 8px; font-size: 1.0rem; padding: 0.45rem 1.1rem;}
.stTextInput>div>input, .stNumberInput>div>input, .stSelectbox>div>div {border-radius: 8px; font-size: 1.0rem;}
.stTable, .stDataFrame {background: #fff; border-radius: 12px; box-shadow: 0 2px 8px rgba(0,0,0,0.04);}
.stCard {background: #fff; border-radius: 12px; box-shadow: 0 2px 12px rgba(0,0,0,0.07); padding: 1rem; margin-bottom: 1rem;}
.mealplan-table-card {background: #fff; color: #222; border-radius: 12px; padding: 1rem; margin-bottom: 1rem; overflow-x:auto;}
</style>
""", unsafe_allow_html=True)

# ---------------------- Gemini & Models ----------------------
# NOTE: Replace with env var in production
genai.configure(api_key="AIzaSyDWmio3eTjB4iC_YL_vP7jb0RXdizwYz64")

# Session-state init
if "running" not in st.session_state:
    st.session_state.running = False
if "show_plan" not in st.session_state:
    st.session_state.show_plan = False
if "stop_event" not in st.session_state:
    st.session_state.stop_event = None
if "reminder_thread" not in st.session_state:
    st.session_state.reminder_thread = None
if "intake_history" not in st.session_state:
    st.session_state.intake_history = []
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []

# Load models & label encoders (keep file names)
model_cal = joblib.load("model_calories.pkl")
model_water = joblib.load("model_water.pkl")
le_dict = joblib.load("label_encoders.pkl")

# ---------------------- Helper utilities ----------------------
def safe_transform(le, value):
    try:
        if value not in le.classes_:
            return le.transform(["Unknown"])[0]
        return le.transform([value])[0]
    except Exception:
        # fallback: if encoder doesn't exist or value unknown
        return 0

# Sound & notification helpers
try:
    if platform.system() == "Windows":
        import winsound
    else:
        from playsound import playsound
except Exception:
    winsound = None

def play_sound():
    try:
        if platform.system() == "Windows" and winsound:
            winsound.Beep(1000, 400)
        else:
            playsound("alarm.mp3", block=False)
    except Exception:
        pass

def send_notification(title, message):
    try:
        notification.notify(title=title, message=message, timeout=7)
    except Exception:
        pass
    play_sound()

def start_reminders(reminder_hours, stop_event):
    while not stop_event.is_set():
        now = datetime.now().strftime("%H:%M")
        if now in reminder_hours:
            send_notification("💧 Hydration Reminder", f"Time to drink water! ({now})")
            for _ in range(60):
                if stop_event.is_set():
                    return
                time.sleep(1)
        else:
            for _ in range(30):
                if stop_event.is_set():
                    return
                time.sleep(1)

# ---------------------- Daily Health Tip & Title (top of page) ----------------------
reminders_list = [
    "💧 Drink a glass of water now — hydration keeps your energy up!",
    "🍎 Eat fruits and veggies daily — your body will thank you.",
    "🚶 Take a 10-minute walk after meals to boost digestion.",
    "😴 Sleep at least 7 hours for better recovery.",
    "🧘 Take a deep breath and stretch — stress melts away!",
    "🥗 Add more fiber to your diet for a healthier gut.",
    "💪 Keep moving! Even small activity burns calories.",
    "🌞 Morning sunlight boosts Vitamin D and your mood!"
]
daily_tip = random.choice(reminders_list)

# Page header
st.markdown(f"### 🌟 Daily Health Tip: {daily_tip}")
st.title("🧠 Smart Diet Planner")
st.markdown("---")

# ---------------------- Tabs Layout ----------------------
tab_dashboard, tab_meal, tab_diet, tab_progress, tab_assistant = st.tabs(
    ["🏠 Dashboard", "🤖 AI Meal Generator", "🍽️ Diet Planner", "💧 Progress Tracker", "🤖 AI Assistant"]
)

# ---------- DASHBOARD TAB ----------
with tab_dashboard:
    st.header("Dashboard")
    # Metrics and quick results area
    col_a, col_b, col_c = st.columns(3)
    # If user has generated plan previously, show metrics, else show placeholders
    calories_val = st.session_state.get("last_calories", None)
    water_val = st.session_state.get("last_water", None)
    bmi_val = st.session_state.get("last_bmi", None)

    with col_a:
        if calories_val:
            st.metric("Calorie Goal (kcal/day)", f"{calories_val:.0f}")
        else:
            st.metric("Calorie Goal (kcal/day)", "—")

    with col_b:
        if water_val:
            st.metric("Water Goal (L/day)", f"{water_val:.2f}")
        else:
            st.metric("Water Goal (L/day)", "—")

    with col_c:
        if bmi_val:
            st.metric("Latest BMI", f"{bmi_val:.2f}")
        else:
            st.metric("Latest BMI", "—")

    st.markdown("---")
    st.subheader("Your Health Recommendations")
    if st.session_state.get("recommendation_text"):
        st.markdown(st.session_state.recommendation_text, unsafe_allow_html=True)
    else:
        st.info("Generate your plan in the Diet Planner tab to see personalized recommendations here.")

# ---------- DIET PLANNER TAB ----------

# ---------- AI MEAL GENERATOR TAB ----------
with tab_meal:
    st.header("AI Meal Generator")
    st.write("Generate a day-wise meal plan based on your preferences.")
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        num_days = st.number_input("Days", min_value=1, max_value=7, value=3, key="num_days")
    with c2:
        diet_type = st.selectbox("Diet Type", ["Vegetarian", "Vegan", "High-Protein", "Low-Carb"], key="diet_type")
    with c3:
        daily_kcal = st.number_input("Daily Calorie Target", min_value=1000, max_value=4000, value=2000, key="daily_kcal")
    with c4:
        budget = st.text_input("Budget/Cooking Time", placeholder="e.g. under 30 min or ₹300/day", key="budget")

    meal_prompt = f"Generate a {num_days}-day {diet_type.lower()} meal plan under {daily_kcal} kcal/day. "
    if budget:
        meal_prompt += f"Keep budget/cooking time: {budget}. "
    meal_prompt += "Format as a table: Day, Breakfast, Lunch, Dinner, Total kcal."

    if st.button("Generate Meal Plan", key="generate_meal"):
        with st.spinner("Generating meal plan..."):
            try:
                model = genai.GenerativeModel("models/gemini-2.5-pro")
                response = model.generate_content(meal_prompt)
                meal_text = response.text.strip()
                st.markdown("#### 🍽️ Your AI-Generated Meal Plan")
                st.markdown("<div class='mealplan-table-card'>" + meal_text + "</div>", unsafe_allow_html=True)
            except Exception as e:
                st.error(f"Meal generation failed: {e}")

# ---------- DIET PLANNER TAB ----------
with tab_diet:
    st.header("Personal Information & Diet Planner")
    with st.expander("Enter your details: 👤 Personal Information", expanded=True):
        cols = st.columns(3)
        with cols[0]:
            age = st.number_input("Age (years)", min_value=10, max_value=100, key="age")
            gender = st.selectbox("Gender", ["Select...", "Male", "Female", "Other"], key="gender")
            height = st.number_input("Height (cm)", min_value=100, max_value=250, key="height")
        with cols[1]:
            weight = st.number_input("Weight (kg)", min_value=30, max_value=200, key="weight")
            stress = st.number_input("Stress Level (1-10)", min_value=1, max_value=10, key="stress")
            sleep = st.number_input("Sleep Hours per Day", min_value=1, max_value=12, key="sleep")
        with cols[2]:
            smoker = st.selectbox("Smoker?", ["Select...", "No", "Yes"], key="smoker")
            exercise = st.selectbox("Exercise Frequency", ["Select...", "Unknown", "Rarely", "Sometimes", "Often"], key="exercise")
            diet_quality = st.selectbox("Diet Quality", ["Select...", "Poor", "Average", "Good"], key="diet_quality")
            alcohol = st.selectbox("Alcohol Consumption", ["Select...", "Unknown", "Rarely", "Sometimes", "Often"], key="alcohol")
            chronic = st.selectbox("Chronic Disease?", ["Select...", "No", "Yes"], key="chronic")

        st.markdown("")  # spacing
        if st.button("Get My Plan", key="get_plan"):
            # Build input dataframe and make predictions (preserve your logic)
            bmi = weight / (height/100)**2 if height else 0
            input_data = {
                'Age':[age],
                'Gender':[safe_transform(le_dict['Gender'], gender)],
                'Height_cm':[height],
                'Weight_kg':[weight],
                'BMI':[bmi],
                'Smoker':[safe_transform(le_dict['Smoker'], smoker)],
                'Exercise_Freq':[safe_transform(le_dict['Exercise_Freq'], exercise)],
                'Diet_Quality':[safe_transform(le_dict['Diet_Quality'], diet_quality)],
                'Alcohol_Consumption':[safe_transform(le_dict['Alcohol_Consumption'], alcohol)],
                'Chronic_Disease':[safe_transform(le_dict['Chronic_Disease'], chronic)],
                'Stress_Level':[stress],
                'Sleep_Hours':[sleep]
            }
            input_df = pd.DataFrame(input_data)
            try:
                calories = model_cal.predict(input_df)[0]
                water = model_water.predict(input_df)[0]
            except Exception as e:
                st.error(f"Prediction failed: {e}")
                calories = None
                water = None

            # Save results to session so other tabs can read
            st.session_state.last_calories = calories
            st.session_state.last_water = water
            st.session_state.last_bmi = bmi
            st.session_state.show_plan = True

            # also save readable recommendation text to show on Dashboard
            rec_text = ""
            if bmi:
                if bmi < 18.5:
                    rec_text += "⚠️ You are underweight. Consider a calorie-rich balanced diet.\n\n"
                elif 18.5 <= bmi < 24.9:
                    rec_text += "✅ Your weight is normal. Maintain your healthy lifestyle.\n\n"
                elif 25 <= bmi < 29.9:
                    rec_text += "⚠️ You are overweight. Focus on balanced diet and moderate exercise.\n\n"
                else:
                    rec_text += "❌ You are obese. Follow a controlled diet and regular exercise.\n\n"
            if water is not None:
                if water < 2.5:
                    rec_text += f"💧 Your recommended water intake is {water:.2f} liters. Increase your daily water intake!\n\n"
                else:
                    rec_text += f"💧 Your recommended water intake is {water:.2f} liters. You are well hydrated!\n\n"
            if calories is not None:
                rec_text += f"🔥 Your recommended daily calorie intake is {calories:.0f} kcal.\n\n"
            st.session_state.recommendation_text = rec_text
            st.success("Plan generated and saved — view results in Progress Tracker or Dashboard.")

# ---------- PROGRESS TRACKER TAB ----------
with tab_progress:
    st.header("Track Your Daily Intake & Progress")

    # show quick recommendation summary if plan exists
    if st.session_state.get("show_plan") and st.session_state.get("last_calories"):
        st.subheader("Quick Summary")
        c1, c2, c3 = st.columns(3)
        c1.metric("Calorie Goal", f"{st.session_state.last_calories:.0f} kcal")
        c2.metric("Water Goal", f"{st.session_state.last_water:.2f} L")
        c3.metric("BMI", f"{st.session_state.last_bmi:.2f}")

    st.markdown("---")

    # Input today's intake
    st.subheader("📥 Today's Intake")
    col_w, col_k = st.columns([1,1])
    with col_w:
        daily_water = st.number_input("Today's Water Intake (liters)", min_value=0.0, step=0.1, key="daily_water")
    with col_k:
        daily_calories = st.number_input("Today's Calorie Intake (kcal)", min_value=0, step=10, key="daily_calories")

    if st.button("Save Today's Intake", key="save_intake"):
        st.session_state.intake_history.append({
            'date': datetime.now().strftime('%Y-%m-%d'),
            'water': daily_water,
            'calories': daily_calories,
            'goal_water': st.session_state.get("last_water", 0),
            'goal_calories': st.session_state.get("last_calories", 0)
        })
        st.success("Today's intake saved!")


    # Show separate comparison graphs for water and calorie intake
    if st.session_state.intake_history:
        st.markdown("### 💧 Water Intake Progress vs Goal & 🔥 Calorie Intake Progress vs Goal")
        dates = [entry['date'] for entry in st.session_state.intake_history]
        water_values = [entry['water'] for entry in st.session_state.intake_history]
        goal_water_values = [entry['goal_water'] for entry in st.session_state.intake_history]
        kcal_values = [entry['calories'] for entry in st.session_state.intake_history]
        goal_kcal_values = [entry['goal_calories'] for entry in st.session_state.intake_history]

        col_graph1, col_graph2 = st.columns(2)
        with col_graph1:
            water_fig = go.Figure()
            water_fig.add_trace(go.Bar(x=dates, y=water_values, name='Water Intake (L)', marker_color='blue'))
            if any(goal_water_values):
                water_fig.add_trace(go.Bar(x=dates, y=goal_water_values, name='Water Goal (L)', marker_color='lightgray'))
            water_fig.update_layout(barmode='group', xaxis_title='Date', yaxis_title='Liters', title='Water Intake vs Goal')
            st.plotly_chart(water_fig, use_container_width=True)

        with col_graph2:
            kcal_fig = go.Figure()
            kcal_fig.add_trace(go.Bar(x=dates, y=kcal_values, name='Calorie Intake (kcal)', marker_color='orange'))
            if any(goal_kcal_values):
                kcal_fig.add_trace(go.Bar(x=dates, y=goal_kcal_values, name='Calorie Goal (kcal)', marker_color='gold'))
            kcal_fig.update_layout(barmode='group', xaxis_title='Date', yaxis_title='Kcal', title='Calorie Intake vs Goal')
            st.plotly_chart(kcal_fig, use_container_width=True)

        # show today's percentage
        today = datetime.now().strftime('%Y-%m-%d')
        today_entry = next((entry for entry in st.session_state.intake_history if entry['date'] == today), None)
        if today_entry:
            percent_water = min(100, int((today_entry['water'] / today_entry['goal_water']) * 100)) if today_entry['goal_water'] else 0
            percent_kcal = min(100, int((today_entry['calories'] / today_entry['goal_calories']) * 100)) if today_entry['goal_calories'] else 0
            st.info(f"You met {percent_water}% of your hydration goal and {percent_kcal}% of your calorie goal today")

    # Water schedule and automatic reminders
    st.markdown("---")
    st.subheader("Water Schedule & Reminders")

    # derive water schedule if plan exists
    water_goal = st.session_state.get("last_water", None)
    if water_goal:
        total_ml = water_goal * 1000
        reminder_count = 7
        per_reminder_ml = int(total_ml / reminder_count)
        reminder_hours = ["07:00", "09:00", "11:00", "13:00", "15:00", "17:00", "19:00"]

        st.success(f"💦 Drink about **{per_reminder_ml} ml** every ~2 hours to reach **{water_goal:.2f} L/day**.")
        # Override table font color to black for visibility
        st.markdown("""
            <style>
            .stTable, .stTable th, .stTable td {
                color: #111 !important;
            }
            .stTable td:nth-child(2) {
                text-align: center !important;
            }
            </style>
        """, unsafe_allow_html=True)
        reminder_table = pd.DataFrame({
            "Time": reminder_hours,
            "Amount (ml)": [per_reminder_ml] * reminder_count,
            "Task": ["Drink Water 💧"] * reminder_count
        })
        st.table(reminder_table)
    else:
        st.info("Generate a plan in Diet Planner to get a water schedule.")

    st.subheader("🔔 Automatic Water Reminders")
    test_mode = st.checkbox("Test mode (every 10 sec for demo)", value=False)

    col1, col2 = st.columns(2)
    with col1:
        if st.button("Start Automatic Water Reminders", key="start_reminders"):
            if st.session_state.running:
                st.warning("Reminders already running.")
            else:
                stop_event = threading.Event()
                st.session_state.stop_event = stop_event

                def test_thread(ev):
                    for i in range(7):
                        if ev.is_set():
                            return
                        time.sleep(10)
                        send_notification("💧 Test Reminder", f"Reminder #{i+1}")
                    st.session_state.running = False

                if test_mode:
                    t = threading.Thread(target=test_thread, args=(stop_event,), daemon=True)
                else:
                    t = threading.Thread(target=start_reminders, args=(["07:00","09:00","11:00","13:00","15:00","17:00","19:00"], stop_event), daemon=True)

                t.start()
                st.session_state.reminder_thread = t
                st.session_state.running = True
                st.success("Reminders started — keep this tab open.")

    with col2:
        if st.button("Stop Reminders", key="stop_reminders"):
            if st.session_state.running and st.session_state.stop_event:
                st.session_state.stop_event.set()
                st.session_state.running = False
                st.success("Reminders stopped.")
            else:
                st.info("No reminders currently running.")

# ---------- AI ASSISTANT TAB ----------
with tab_assistant:
    st.header("🤖 AI Health Assistant (Asha)")

    SYSTEM_PROMPT = """You are Asha, a friendly AI health assistant.
You help students with practical diet, hydration, and wellness tips.
Give concise, motivating, and easy-to-understand advice.
If user asks something medical, gently recommend consulting a doctor.
Prefer vegetarian food suggestions unless asked otherwise.
"""

    # Show the user's plan context
    col_ctx1, col_ctx2 = st.columns(2)
    with col_ctx1:
        st.subheader("My Current Health Plan")
        cal_ctx = st.session_state.get("last_calories", None)
        water_ctx = st.session_state.get("last_water", None)
        bmi_ctx = st.session_state.get("last_bmi", None)
        if cal_ctx:
            st.write(f"**Calorie Goal:** {cal_ctx:.0f} kcal/day")
        if water_ctx:
            st.write(f"**Water Goal:** {water_ctx:.2f} L/day")
        if bmi_ctx:
            st.write(f"**BMI:** {bmi_ctx:.2f}")

    # Chat UI
    user_msg = st.text_area("💬 Ask your health assistant:", placeholder="e.g., Suggest a 2000 kcal vegetarian meal plan")
    col_send, col_clear = st.columns([0.18, 0.18])
    with col_send:
        send = st.button("Send Message", key="send_msg")
    with col_clear:
        clear = st.button("Clear Chat", key="clear_chat")

    model = genai.GenerativeModel("models/gemini-2.5-pro")

    if send and user_msg.strip():
        full_prompt = SYSTEM_PROMPT
        full_prompt += f"\nUser context: Calorie goal={cal_ctx if cal_ctx else 'N/A'} kcal/day, Water goal={water_ctx if water_ctx else 'N/A'} L/day.\n"
        full_prompt += f"User: {user_msg}\nAsha:"
        with st.spinner("Asha is thinking..."):
            try:
                response = model.generate_content(full_prompt)
                reply = response.text.strip()
            except Exception as e:
                reply = f"⚠️ Sorry, something went wrong: {e}"
        timestamp = datetime.now().strftime("%H:%M")
        st.session_state.chat_history.append((user_msg, reply, timestamp))

    if clear:
        st.session_state.chat_history = []
        st.success("Chat cleared!")

    if st.session_state.chat_history:
        st.write("### 💬 Chat History")
        for user, ai, t in reversed(st.session_state.chat_history[-16:]):
            st.markdown(f"🧑 **You ({t})**: {user}")
            st.markdown(f"🤖 **Asha:** {ai}")
            st.markdown("---")
