import io
import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.patches as patches
from matplotlib.lines import Line2D
from datetime import date

import requests
import json

SUPABASE_URL = "https://rmdfrysjyzzmkjsxjchy.supabase.co"
SUPABASE_SERVICE_ROLE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InJtZGZyeXNqeXp6bWtqc3hqY2h5Iiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc0NDkxNjE0NSwiZXhwIjoyMDYwNDkyMTQ1fQ.xbP8Owj-Bz0N1KjhjkXvvnJhvbp5OzCNvJOb7-BCFhA"

headers = {
    "apikey": SUPABASE_SERVICE_ROLE_KEY,
    "Authorization": f"Bearer {SUPABASE_SERVICE_ROLE_KEY}",
    "Content-Type": "application/json"
}


PRIMARY_COLOR = "#CE1141"
SECONDARY_COLOR = "#13274F"
BG_COLOR = "#F5F5F5"

st.set_page_config(page_title="🪓 Bullpen Grader", layout="wide")

st.markdown(f"""
    <style>
    .main {{ background-color: {BG_COLOR}; }}
    .stButton > button {{ background-color: {PRIMARY_COLOR}; color: white; font-weight: bold; }}
    .stFileUploader, .stDataFrame {{ background-color: white; }}
    </style>
""", unsafe_allow_html=True)

# 🧱 Page title
st.title("🪓 Braves Bullpen Grader")
st.markdown("Upload your bullpen CSV to grade and visualize pitch effectiveness. Finish pitches are detected from the 'Flag' column.")

# 📂 Upload CSV
uploaded_file = st.file_uploader("Upload your bullpen session CSV", type=["csv"])

if uploaded_file:
    df = pd.read_csv(uploaded_file)
    df_filtered = df[['Pitcher', 'TaggedPitchType', 'PlateLocHeight', 'PlateLocSide', 'Flag']].copy()
    df_filtered['PlateLocHeightInches'] = df_filtered['PlateLocHeight'] * 12
    df_filtered['PlateLocSideInches'] = df_filtered['PlateLocSide'] * 12

    # Constants
    ZONE_BOTTOM = 19.4
    ZONE_TOP = 38.5
    FB_BUFFER_TOP = 40.5
    NFB_BUFFER_BOTTOM = 17.4
    ZONE_SIDE_LEFT = -8.5
    ZONE_SIDE_RIGHT = 8.5

    # Classify pitch types
    fastballs = ["Fastball", "Sinker", "Cutter"]
    df_filtered['IsFastball'] = df_filtered['TaggedPitchType'].apply(lambda x: any(fb.lower() in str(x).lower() for fb in fastballs))
    df_filtered['IsFinish'] = df_filtered['Flag'].astype(str).str.upper() == 'Y'


    # 🧮 Scoring logic
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

    df_filtered['PitchScore'] = df_filtered.apply(score_pitch, axis=1)

    # 🎯 Pitcher filter
    selected_pitcher = st.selectbox("🎯 Filter pitches by pitcher", ["All"] + sorted(df_filtered['Pitcher'].unique().tolist()))
    view_df = df_filtered if selected_pitcher == "All" else df_filtered[df_filtered['Pitcher'] == selected_pitcher]

    # 📊 Pitch-Level Data
    st.subheader("📊 Pitch-Level Data")
    st.dataframe(view_df[['Pitcher', 'TaggedPitchType', 'PlateLocHeightInches', 'PlateLocSideInches', 'IsFinish', 'PitchScore']])

    # 🧾 Pitcher Summary
    summary = df_filtered.groupby('Pitcher')['PitchScore'].agg(['count', 'sum', 'mean']).reset_index()
    summary.columns = ['Pitcher', 'Total Pitches', 'Total Score', 'Avg Score']
    summary['PPP'] = summary['Total Score'] / summary['Total Pitches']

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

    # ⬇️ Download Buttons
    st.download_button("📅 Download Pitch-Level Data", data=df_filtered.to_csv(index=False), file_name="pitch_data.csv", mime="text/csv")
    st.download_button("📅 Download Pitcher Summary", data=summary.to_csv(index=False), file_name="pitcher_summary.csv", mime="text/csv")

        # 🎯 Strike Zone Plot
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
            in_fb_buffer = row['IsFastball'] and ZONE_TOP < y <= FB_BUFFER_TOP
            in_nfb_buffer = not row['IsFastball'] and NFB_BUFFER_BOTTOM <= y < ZONE_BOTTOM

            if score >= 3 and is_finish and (in_fb_buffer or in_nfb_buffer):
                ax.plot(x, y, marker='s', color='green', markersize=14)
            elif score == 0:
                ax.text(x, y, "X", color='red' if is_fb else 'blue', fontsize=14, ha='center', va='center')
            elif score == 1:
                if is_fb:
                    ax.plot(x, y, marker='o', color='red', markersize=10, markerfacecolor='none', markeredgecolor='red')
                else:
                    ax.plot(x, y, marker='o', color='blue', markersize=10, markerfacecolor='none', markeredgecolor='blue')
            elif score == 2:
                if is_fb:
                    ax.plot(x, y, marker='o', color='red', markersize=14, markeredgecolor='red')
                else:
                    ax.plot(x, y, marker='o', color='blue', markersize=14, markeredgecolor='blue')

        # Strike zone box
        ax.add_patch(plt.Rectangle((ZONE_SIDE_LEFT, ZONE_BOTTOM), ZONE_SIDE_RIGHT - ZONE_SIDE_LEFT, ZONE_TOP - ZONE_BOTTOM, edgecolor='black', fill=False, linewidth=2))
        ax.add_patch(patches.Rectangle((-8.5, 20), 17, 17, linewidth=1, edgecolor='black', facecolor='none', linestyle='--', alpha=0.3))

        # Legend
        legend_elements = [
            Line2D([0], [0], marker='o', color='red', label='FB: 1 pt (open)', markerfacecolor='none', markeredgecolor='red', markersize=10),
            Line2D([0], [0], marker='o', color='red', label='FB: 2 pts (solid)', markerfacecolor='red', markeredgecolor='red', markersize=14),
            Line2D([0], [0], marker='o', color='blue', label='NFB: 1 pt (open)', markerfacecolor='none', markeredgecolor='blue', markersize=10),
            Line2D([0], [0], marker='o', color='blue', label='NFB: 2 pts (solid)', markerfacecolor='blue', markeredgecolor='blue', markersize=14),
            Line2D([0], [0], marker='s', color='green', label='Finish Buffer Bonus', linestyle='None', markersize=14),
            Line2D([0], [0], marker='X', color='red', label='FB: 0 pts', linestyle='None', markersize=10),
            Line2D([0], [0], marker='X', color='blue', label='NFB: 0 pts', linestyle='None', markersize=10),
        ]
        ax.legend(handles=legend_elements, loc='upper right', frameon=True)

        ax.set_xlim(-10, 10)
        ax.set_ylim(18, 42)
        ax.set_xlabel("Plate Side (in)")
        ax.set_ylabel("Plate Height (in)")
        ax.set_title(f"{selected_pitcher} Strike Zone")
        ax.grid(True, linestyle='--', alpha=0.3)
        ax.set_facecolor("#f9f9f9")

        st.pyplot(fig)

        # PDF Export
        pdf_buffer = io.BytesIO()
        fig.savefig(pdf_buffer, format="pdf", bbox_inches="tight")
        pdf_buffer.seek(0)

        st.download_button(
            label="📥 Download Strike Zone Plot as PDF",
            data=pdf_buffer,
            file_name=f"Bullpen_Grader_Report_{selected_pitcher.replace(' ', '_')}.pdf",
            mime="application/pdf"
        )

    # ✅ Save session results to Supabase using REST API
    for _, row in summary.iterrows():
        payload = {
            "pitcher_name": str(row['Pitcher']),
            "session_date": date.today().isoformat(),
            "total_pitches": int(row['Total Pitches']),
            "finish_pitches": int(view_df['IsFinish'].sum()),
            "avg_score": float(round(row['Avg Score'], 2)),
            "ppp": float(round(row['PPP'], 2)),
            "grade": str(row['Grade'])
        }

        response = requests.post(
            f"{SUPABASE_URL}/rest/v1/pitcher_sessions",
            headers=headers,
            data=json.dumps(payload)
        )

        if response.status_code in [200, 201]:
            st.success(f"✅ Inserted session for {row['Pitcher']}")
        else:
            st.error(f"❌ Failed to insert {row['Pitcher']}: {response.text}")

    # 🧠 Show the session summary
    total = len(view_df)
    finish_count = view_df['IsFinish'].sum()
    avg_score = view_df['PitchScore'].mean().round(2)
    st.markdown(f"**Summary**: {total} Pitches | {finish_count} Finish | Avg Score: {avg_score}")

# 📖 View Past Sessions

st.header("📖 Past Pitcher Sessions")

if st.button("🔄 Load Past Sessions"):
    response = requests.get(
        f"{SUPABASE_URL}/rest/v1/pitcher_sessions?select=*",
        headers={
            "apikey": SUPABASE_SERVICE_ROLE_KEY,
            "Authorization": f"Bearer {SUPABASE_SERVICE_ROLE_KEY}"
        }
    )

    if response.status_code == 200:
        past_sessions = pd.DataFrame(response.json())

        if not past_sessions.empty:
            past_sessions['session_date'] = pd.to_datetime(past_sessions['session_date']).dt.date
            past_sessions = past_sessions.sort_values(by="session_date", ascending=False)

            st.dataframe(past_sessions)

            csv = past_sessions.to_csv(index=False).encode('utf-8')
            st.download_button(
                label="📥 Download Full Session History",
                data=csv,
                file_name='past_pitcher_sessions.csv',
                mime='text/csv',
            )
        else:
            st.info("No sessions found yet.")
    else:
        st.error(f"Failed to load sessions: {response.text}")

