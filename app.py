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
st.set_page_config(page_title="✏️  Bullpen Grader", layout="wide")
st.markdown(f"""
    <style>
    .main {{ background-color: {BG_COLOR}; }}
    .stButton > button {{ background-color: {PRIMARY_COLOR}; color: white; font-weight: bold; }}
    .stFileUploader, .stDataFrame {{ background-color: white; }}
    </style>
""", unsafe_allow_html=True)

# Sidebar Navigation
page = st.sidebar.radio("Go to:", ["➕ Upload New Session", "📖 View Past Sessions", "📈 Historical Trends"])

# Functions
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
        session_date = date_match.group(1) if date_match else date.today().isoformat()

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

        st.subheader("🎯 Strike Zone Plot")
        if selected_pitcher == "All":
            st.info("Select a specific pitcher to view their strike zone plot.")
        else:
            fig, ax = plt.subplots(figsize=(6, 8))
            pitcher_df = view_df.copy()
            for _, row in pitcher_df.iterrows():
                x = row['PlateLocSideInches']
                y = row['PlateLocHeightInches']
                is_fb = row['IsFastball']
                score = row['PitchScore']
                is_finish = row['IsFinish']
                in_fb_buffer = is_fb and ZONE_TOP < y <= FB_BUFFER_TOP
                in_nfb_buffer = not is_fb and NFB_BUFFER_BOTTOM <= y < ZONE_BOTTOM

                if score >= 3 and is_finish and (in_fb_buffer or in_nfb_buffer):
                    ax.plot(x, y, marker='s', color='green', markersize=14)
                elif score == 0:
                    ax.text(x, y, "X", color='red' if is_fb else 'blue', fontsize=14, ha='center', va='center')
                elif score == 1:
                    ax.plot(x, y, marker='o', color='red' if is_fb else 'blue', markersize=10, markerfacecolor='none')
                elif score == 2:
                    ax.plot(x, y, marker='o', color='red' if is_fb else 'blue', markersize=14)

            ax.add_patch(plt.Rectangle((ZONE_SIDE_LEFT, ZONE_BOTTOM), ZONE_SIDE_RIGHT - ZONE_SIDE_LEFT, ZONE_TOP - ZONE_BOTTOM, edgecolor='black', fill=False, linewidth=2))
            ax.set_xlim(-10, 10)
            ax.set_ylim(18, 42)
            ax.set_xlabel("Plate Side (in)")
            ax.set_ylabel("Plate Height (in)")
            ax.set_title(f"{selected_pitcher} Strike Zone")
            ax.grid(True, linestyle='--', alpha=0.3)
            ax.set_facecolor("#f9f9f9")

            legend_elements = [
                Line2D([0], [0], marker='o', color='red', label='FB: 1-2 pts', markerfacecolor='red', markersize=10),
                Line2D([0], [0], marker='o', color='blue', label='NFB: 1-2 pts', markerfacecolor='blue', markersize=10),
                Line2D([0], [0], marker='s', color='green', label='Finish Bonus', linestyle='None', markersize=14),
                Line2D([0], [0], marker='X', color='red', label='FB: 0 pts', linestyle='None', markersize=10),
                Line2D([0], [0], marker='X', color='blue', label='NFB: 0 pts', linestyle='None', markersize=10),
            ]
            ax.legend(handles=legend_elements, loc='upper right', frameon=True)

            st.pyplot(fig)

elif page == "📖 View Past Sessions":
    st.title("📖 Past Pitcher Sessions")
    if st.button("🔄 Load Past Sessions", key="load_past_sessions_button"):
        # 1) Confirm the request URL
        st.write("Requesting URL:", f"{SUPABASE_URL}/rest/v1/pitcher_sessions?select=*")

# 2) Show exactly what headers you’re sending
        st.write("Outgoing headers:", headers)

# 3) (Optional) Show repr of the key to catch stray whitespace
        st.write("Key repr:", repr(SUPABASE_SERVICE_ROLE_KEY))

        response = requests.get(f"{SUPABASE_URL}/rest/v1/pitcher_sessions?select=*", headers=headers)
        if response.status_code == 200:
            past_sessions = pd.DataFrame(response.json())
            st.dataframe(past_sessions)
        else:
            st.error("Failed to load sessions")
            st.write(response.status_code, response.text)

elif page == "📈 Historical Trends":
    st.title("📈 Historical Player Trends")

    # 1) Fetch all sessions
    response = requests.get(
        f"{SUPABASE_URL}/rest/v1/pitcher_sessions?select=*",
        headers=headers
    )
    if response.status_code != 200:
        st.error("Failed to load sessions")
        st.stop()

    # 2) Load into DataFrame and parse dates
    past_sessions = pd.DataFrame(response.json())
    if past_sessions.empty:
        st.info("No sessions yet.")
        st.stop()

    past_sessions['session_date'] = pd.to_datetime(
        past_sessions['session_date']
    ).dt.date

    # 3) Player picker
    player_names = sorted(past_sessions['pitcher_name'].unique())
    selected_player = st.selectbox("🎯 Select Player", player_names)

    # 4) Filter & sort that player’s data
    player_data = (
        past_sessions[past_sessions['pitcher_name'] == selected_player]
        .sort_values('session_date')
    )

    # 5) Plot discrete PPP points on actual session dates
    player_data = player_data.reset_index(drop=True)
    dates = player_data['session_date'].astype(str)
    ppp   = player_data['ppp']
    x = list(range(len(player_data)))

    # Assign letter grades for annotation
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

    grades = ppp.apply(assign_grade)

    # Plot with even spacing
    fig, ax = plt.subplots(figsize=(8, 4))
    ax.plot(x, ppp, marker='o', linestyle='', label='Points Per Pitch', color='#1f77b4')

    # Annotate with grades
    for i, grade in enumerate(grades):
        ax.text(x[i], ppp[i] + 0.025, grade, ha='center', va='bottom', fontsize=10, color='black')

    # Customize x-axis ticks
    ax.set_xticks(x)
    ax.set_xticklabels(dates, rotation=45, ha='right')

    # Labels and title
    ax.set_xlabel("Session Date")
    ax.set_ylabel("Points Per Pitch")
    ax.set_title(f"{selected_player} – Session History")
    ax.legend(loc="upper left")

    st.pyplot(fig)






