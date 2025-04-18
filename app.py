import io
import re
import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.patches as patches
from matplotlib.lines import Line2D
from datetime import date
import requests
import json

# Constants
SUPABASE_URL = "https://rmdfrysjyzzmkjsxjchy.supabase.co"
SUPABASE_SERVICE_ROLE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InJtZGZyeXNqeXp6bWtqc3hqY2h5Iiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc0NDkxNjE0NSwiZXhwIjoyMDYwNDkyMTQ1fQ.xbP8Owj-Bz0N1KjhjkXvvnJhvbp5OzCNvJOb7-BCFhA"
headers = {
    "apikey": SUPABASE_SERVICE_ROLE_KEY,
    "Authorization": f"Bearer {SUPABASE_SERVICE_ROLE_KEY}",
    "Content-Type": "application/json"
}

# Strike Zone Settings
ZONE_BOTTOM = 19.4
ZONE_TOP = 38.5
FB_BUFFER_TOP = 40.5
NFB_BUFFER_BOTTOM = 17.4
ZONE_SIDE_LEFT = -8.5
ZONE_SIDE_RIGHT = 8.5
fastballs = ["Fastball", "Sinker", "Cutter"]

# Streamlit Page Setup
PRIMARY_COLOR = "#CE1141"
SECONDARY_COLOR = "#13274F"
BG_COLOR = "#F5F5F5"
st.set_page_config(page_title="🢫 Bullpen Grader", layout="wide")
st.markdown(f"""
    <style>
    .main {{ background-color: {BG_COLOR}; }}
    .stButton > button {{ background-color: {PRIMARY_COLOR}; color: white; font-weight: bold; }}
    .stFileUploader, .stDataFrame {{ background-color: white; }}
    </style>
""", unsafe_allow_html=True)

# Sidebar Navigation
page = st.sidebar.radio("Go to:", ["➕ Upload New Session", "📖 View Past Sessions", "📈 Historical Trends"])

# Scoring and Grading Functions
def score_pitch(row):
    height = row['PlateLocHeightInches']
    side = row['PlateLocSideInches']
    is_fb = row['IsFastball']
    is_finish = row['IsFinish']
    if pd.isnull(height) or pd.isnull(side):
        return 0
    if not (ZONE_SIDE_LEFT <= side <= ZONE_SIDE_RIGHT):
        return 0
    score = 0
    buffer_zone = False
    midline = (ZONE_TOP + ZONE_BOTTOM) / 2
    if is_fb:
        if ZONE_BOTTOM <= height <= ZONE_TOP:
            score += 2 if height > midline else 1
        elif ZONE_TOP < height <= FB_BUFFER_TOP:
            score += 1
            buffer_zone = True
    else:
        if ZONE_BOTTOM <= height <= ZONE_TOP:
            score += 2 if height < midline else 1
        elif NFB_BUFFER_BOTTOM <= height < ZONE_BOTTOM:
            score += 1
            buffer_zone = True
    if is_finish and buffer_zone:
        score += 1
    return score

def assign_grade(pct):
    if pct > 0.8:
        return "A"
    elif pct > 0.65:
        return "B"
    elif pct > 0.5:
        return "C"
    elif pct > 0.35:
        return "D"
    else:
        return "F"

# ----------------- Pages ----------------- #

if page == "➕ Upload New Session":
    st.title("🪓 Braves Bullpen Grader")
    st.markdown("Upload your bullpen CSV to grade and visualize pitch effectiveness. Finish pitches are detected from the 'Flag' column.")

    uploaded_file = st.file_uploader("Upload your bullpen session CSV", type=["csv"], key="upload_new_session_file")

    if uploaded_file:
        df = pd.read_csv(uploaded_file)
        
        uploaded_filename = uploaded_file.name
        date_match = re.search(r'(\d{4}-\d{2}-\d{2})', uploaded_filename)
        if date_match:
            session_date = date_match.group(1)
        else:
            session_date = date.today().isoformat()

        df_filtered = df[['Pitcher', 'TaggedPitchType', 'PlateLocHeight', 'PlateLocSide', 'Flag']].copy()
        df_filtered['PlateLocHeightInches'] = df_filtered['PlateLocHeight'] * 12
        df_filtered['PlateLocSideInches'] = df_filtered['PlateLocSide'] * 12
        df_filtered['IsFastball'] = df_filtered['TaggedPitchType'].apply(lambda x: any(fb.lower() in str(x).lower() for fb in fastballs))
        df_filtered['IsFinish'] = df_filtered['Flag'].astype(str).str.upper() == 'Y'
        df_filtered['PitchScore'] = df_filtered.apply(score_pitch, axis=1)

        selected_pitcher = st.selectbox("🎯 Filter pitches by pitcher", ["All"] + sorted(df_filtered['Pitcher'].unique().tolist()))
        view_df = df_filtered if selected_pitcher == "All" else df_filtered[df_filtered['Pitcher'] == selected_pitcher]

        st.subheader("📊 Pitch-Level Data")
        st.dataframe(view_df[['Pitcher', 'TaggedPitchType', 'PlateLocHeightInches', 'PlateLocSideInches', 'IsFinish', 'PitchScore']])

        summary = df_filtered.groupby('Pitcher')['PitchScore'].agg(['count', 'sum', 'mean']).reset_index()
        summary.columns = ['Pitcher', 'Total Pitches', 'Total Score', 'Avg Score']
        summary['PPP'] = summary['Total Score'] / summary['Total Pitches']

        max_possible = df_filtered.groupby('Pitcher').apply(
            lambda x: sum((x['IsFastball'] & (x['PlateLocHeightInches'] > ZONE_TOP) & (x['PlateLocHeightInches'] <= FB_BUFFER_TOP)) |
                          (~x['IsFastball'] & (x['PlateLocHeightInches'] < ZONE_BOTTOM) & (x['PlateLocHeightInches'] >= NFB_BUFFER_BOTTOM)))
        ).reset_index(name="FinishBufferCount")

        pitch_counts = df_filtered.groupby('Pitcher')['PitchScore'].count().reset_index(name='PitchCount')
        max_possible['MaxPossible'] = pitch_counts['PitchCount'] + max_possible['FinishBufferCount']

        summary = pd.merge(summary, max_possible[['Pitcher', 'MaxPossible']], on="Pitcher")
        summary['Grade %'] = summary['Total Score'] / summary['MaxPossible']
        summary['Grade'] = summary['Grade %'].apply(assign_grade)

        st.subheader("Pitcher Summary & Grades")
        st.dataframe(summary[['Pitcher', 'Total Pitches', 'Total Score', 'Avg Score', 'PPP', 'Grade']])

        st.download_button("📅 Download Pitch-Level Data", data=df_filtered.to_csv(index=False), file_name="pitch_data.csv", mime="text/csv")
        st.download_button("📅 Download Pitcher Summary", data=summary.to_csv(index=False), file_name="pitcher_summary.csv", mime="text/csv")

        for _, row in summary.iterrows():
            pitcher_name = str(row['Pitcher'])
            check_response = requests.get(
                f"{SUPABASE_URL}/rest/v1/pitcher_sessions?pitcher_name=eq.{pitcher_name}&session_date=eq.{session_date}",
                headers=headers
            )

            if check_response.status_code == 200 and len(check_response.json()) == 0:
                payload = {
                    "pitcher_name": pitcher_name,
                    "session_date": session_date,
                    "total_pitches": int(row['Total Pitches']),
                    "finish_pitches": int(view_df['IsFinish'].sum()),
                    "avg_score": float(round(row['Avg Score'], 2)),
                    "ppp": float(round(row['PPP'], 2)),
                    "grade": str(row['Grade'])
                }
                insert_response = requests.post(
                    f"{SUPABASE_URL}/rest/v1/pitcher_sessions",
                    headers=headers,
                    data=json.dumps(payload)
                )
                if insert_response.status_code in [200, 201]:
                    st.success(f"✅ Inserted session for {pitcher_name}")
                else:
                    st.error(f"❌ Failed to insert {pitcher_name}: {insert_response.text}")
            else:
                st.info(f"⚠️ Session for {pitcher_name} on {session_date} already exists — skipping.")

elif page == "📖 View Past Sessions":
    st.title("📖 Past Pitcher Sessions")
    if st.button("🔄 Load Past Sessions", key="load_past_sessions_button"):
        response = requests.get(
            f"{SUPABASE_URL}/rest/v1/pitcher_sessions?select=*",
            headers=headers
        )
        if response.status_code == 200:
            past_sessions = pd.DataFrame(response.json())
            if not past_sessions.empty:
                past_sessions['session_date'] = pd.to_datetime(past_sessions['session_date']).dt.date
                past_sessions = past_sessions.sort_values(by="session_date", ascending=False)
                st.dataframe(past_sessions)
                csv = past_sessions.to_csv(index=False).encode('utf-8')
                st.download_button("📥 Download Full Session History", data=csv, file_name='past_pitcher_sessions.csv', mime='text/csv')
            else:
                st.info("No sessions found yet.")
        else:
            st.error(f"Failed to load sessions: {response.text}")

elif page == "📈 Historical Trends":
    st.title("📈 Historical Player Trends")
    response = requests.get(
        f"{SUPABASE_URL}/rest/v1/pitcher_sessions?select=*",
        headers=headers
    )
    if response.status_code == 200:
        past_sessions = pd.DataFrame(response.json())
        if not past_sessions.empty:
            past_sessions['session_date'] = pd.to_datetime(past_sessions['session_date']).dt.date
            player_names = sorted(past_sessions['pitcher_name'].unique())
            selected_player = st.selectbox("🎯 Select Player", player_names)

            player_data = past_sessions[past_sessions['pitcher_name'] == selected_player]
            player_data = player_data.sort_values('session_date')

            fig, ax = plt.subplots(figsize=(10, 5))
            ax.plot(player_data['session_date'], player_data['avg_score'], marker='o', label='Avg Score')
            ax.plot(player_data['session_date'], player_data['ppp'], marker='s', linestyle='--', label='Points Per Pitch')

            ax.set_title(f"{selected_player} - Historical Bullpen Trends")
            ax.set_xlabel("Session Date")
            ax.set_ylabel("Score")
            ax.legend()
            ax.grid(True)

            st.pyplot(fig)

            csv = player_data.to_csv(index=False).encode('utf-8')
            st.download_button("📥 Download Player History", data=csv, file_name=f'{selected_player}_history.csv', mime='text/csv')
        else:
            st.info("No sessions found yet.")
    else:
        st.error(f"Failed to load sessions: {response.text}")
