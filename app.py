import io
import re
import streamlit as st
import pandas as pd
import numpy as np
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
        # ── BULK INSERT PITCHES INTO Supabase ──
# 1) Rename & select only the columns our table expects:
records = (
    df_filtered
    .rename(columns={
        'Pitcher': 'pitcher_name',
        'TaggedPitchType': 'tagged_pitch_type',
        'PlateLocHeightInches': 'plate_loc_height_inches',
        'PlateLocSideInches' : 'plate_loc_side_inches',
        'IsFastball': 'is_fastball',
        'IsFinish': 'is_finish',
        'PitchScore': 'pitch_score'
    })
    [['pitcher_name','tagged_pitch_type',
      'plate_loc_height_inches','plate_loc_side_inches',
      'is_fastball','is_finish','pitch_score']]
)
# 2) Add session_date to every row:
records['session_date'] = session_date

# 3) Fire off the POST to Supabase:
resp = requests.post(
    f"{SUPABASE_URL}/rest/v1/pitches",
    headers=headers,
    json=records.to_dict(orient='records')
)
if resp.status_code not in (200, 201):
    st.error("⚠️ Failed to save pitches:", resp.text)


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
    st.title("📈 Player Dashboard")

    # --- A) Load session summaries for dropdown & date bounds
    r = requests.get(
        f"{SUPABASE_URL}/rest/v1/pitcher_sessions?select=session_date,pitcher_name,ppp",
        headers=headers
    )
    if r.status_code != 200:
        st.error("Failed to load sessions"); st.stop()
    sessions = pd.DataFrame(r.json())
    sessions['session_date'] = pd.to_datetime(sessions['session_date']).dt.date

    if sessions.empty:
        st.info("No sessions yet."); st.stop()

    # --- B) Controls: player, date range, pitch types, heatmap mode
    player = st.selectbox("🎯 Select Player", sorted(sessions['pitcher_name'].unique()))
    dmin, dmax = sessions['session_date'].min(), sessions['session_date'].max()
    start_date, end_date = st.date_input("📅 Date range", value=(dmin, dmax), min_value=dmin, max_value=dmax)

    pitch_choices = ["All", "FB", "SI", "CH", "SPL", "CB", "NFB"]
    sel_types = st.multiselect("⚾ Pitch Types", pitch_choices, default=["All"])
    mode = st.radio("🔥 Heatmap mode", ["Density", "Quality"])

    # --- C) Fetch the raw pitches matching those filters
    filters = [
      f"pitcher_name=eq.{player}",
      f"session_date=gte.{start_date}",
      f"session_date=lte.{end_date}"
    ]
    # build pitch‑type filter
    type_map = {
      "FB": r"^4S$",    # exact 4-seam
      "SI": r"(Sinker|2S)",  
      "CH": r"ChangeUp",
      "SPL": r"Splitter",
      "CB": r"Curve",
      "NFB": None
    }
    if "All" not in sel_types:
        # handle NFB separately
        if "NFB" in sel_types:
            # any not matching FB|SI
            fb_re = "|".join([type_map["FB"], type_map["SI"]])
            filters.append(f"not(tagged_pitch_type.ilike.*{fb_re}*)")
        else:
            regex = "|".join(type_map[t] for t in sel_types)
            filters.append(f"tagged_pitch_type.ilike.*{regex}*")

    qstr = "&".join(filters)
    p = requests.get(
        f"{SUPABASE_URL}/rest/v1/pitches?select=*,pitch_score,plate_loc_side_inches,plate_loc_height_inches&{qstr}",
        headers=headers
    )
    pitches = pd.DataFrame(p.json())

# ── DEBUG: see what actually came back ──
st.write("🔍 Raw /pitches?… response:", p.url)
st.write("🔍 Number of pitches fetched:", len(pitches))
st.write("🔍 Sample rows:", pitches[['plate_loc_side_inches','plate_loc_height_inches','pitch_score']].head())

if pitches.empty:
    st.warning("No pitches in that selection."); st.stop()


    # --- D) Layout & Plots
    col1, col2 = st.columns(2)

    # D1) PPP Trend with letter grades
    with col1:
        player_sess = sessions[(sessions['pitcher_name']==player) &
                               (sessions['session_date'].between(start_date, end_date))] \
                       .sort_values('session_date')
        fig, ax = plt.subplots(figsize=(6,4))
        xs, ys = player_sess['session_date'], player_sess['ppp']
        def grade(p): return ("A" if p>.8 else "B" if p>.65 else "C" if p>.5 else "D" if p>.35 else "F")
        colors = {"A":"green","B":"blue","C":"orange","D":"purple","F":"red"}
        for d,pv in zip(xs, ys):
            g = grade(pv)
            ax.scatter(d, pv, color=colors[g], s=100)
            ax.text(d, pv+0.02, g, ha='center')
        ax.set_xticks(xs); fig.autofmt_xdate()
        ax.set_xlabel("Date"); ax.set_ylabel("Points Per Pitch")
        ax.set_title(f"{player} — PPP Trend")
        st.pyplot(fig)

    # D2) Strike‑Zone Heatmap
    with col2:
        fig2, ax2 = plt.subplots(figsize=(6,6))
        x = pitches['plate_loc_side_inches']
        y = pitches['plate_loc_height_inches']
        if mode=="Density":
            hb = ax2.hexbin(x, y, gridsize=20, mincnt=1)
            fig2.colorbar(hb, ax=ax2, label="Pitch count")
        else:
            hb = ax2.hexbin(
              x, y,
              C=pitches['pitch_score'],
              reduce_C_function=np.mean,
              gridsize=20, mincnt=1
            )
            fig2.colorbar(hb, ax=ax2, label="Avg PitchScore")
        ax2.add_patch(patches.Rectangle(
            (ZONE_SIDE_LEFT, ZONE_BOTTOM),
            ZONE_SIDE_RIGHT - ZONE_SIDE_LEFT,
            ZONE_TOP - ZONE_BOTTOM,
            fill=False, edgecolor='black', linewidth=2
        ))
        ax2.set_xlim(ZONE_SIDE_LEFT*1.2, ZONE_SIDE_RIGHT*1.2)
        ax2.set_ylim(NFB_BUFFER_BOTTOM*0.9, FB_BUFFER_TOP*1.05)
        ax2.set_xlabel("Side (in)"); ax2.set_ylabel("Height (in)")
        ax2.set_title(f"{player} — Strike‑Zone HeatMap ({mode})")
        st.pyplot(fig2)






