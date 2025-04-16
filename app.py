import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns

# Set color palette
PRIMARY_COLOR = "#CE1141"  # Braves red
SECONDARY_COLOR = "#13274F"  # Braves navy
BG_COLOR = "#F5F5F5"

st.set_page_config(page_title=" 🪓 Bullpen Grader", layout="wide")

st.markdown(f"""
    <style>
    .main {{
        background-color: {BG_COLOR};
    }}
    .stButton > button {{
        background-color: {PRIMARY_COLOR};
        color: white;
        font-weight: bold;
    }}
    .stFileUploader, .stDataFrame {{
        background-color: white;
    }}
    </style>
""", unsafe_allow_html=True)

st.title("🪓 Braves Bullpen Grader")
st.markdown("Upload your bullpen CSV and manually tag 'Finish' pitches for upgraded grading and feedback.")

uploaded_file = st.file_uploader("Upload your bullpen session CSV", type=["csv"])

if uploaded_file:
    df = pd.read_csv(uploaded_file)
    df_filtered = df[['Pitcher', 'TaggedPitchType', 'PlateLocHeight', 'PlateLocSide']].copy()
    df_filtered['PlateLocHeightInches'] = df_filtered['PlateLocHeight'] * 12
    df_filtered['PlateLocSideInches'] = df_filtered['PlateLocSide'] * 12

    # Constants for scoring
    ZONE_BOTTOM = 19.4
    ZONE_TOP = 38.5
    FB_BUFFER_TOP = 40.5
    NFB_BUFFER_BOTTOM = 17.4
    ZONE_SIDE_LEFT = -8.5
    ZONE_SIDE_RIGHT = 8.5

    # Determine if pitch is a fastball
    fastballs = ["Fastball", "Sinker", "Cutter"]
    df_filtered['IsFastball'] = df_filtered['TaggedPitchType'].apply(lambda x: any(fb.lower() in str(x).lower() for fb in fastballs))

    # Initialize session state for Finish checkboxes
    if 'finish_flags' not in st.session_state or len(st.session_state.finish_flags) != len(df_filtered):
        st.session_state.finish_flags = [False] * len(df_filtered)

    # Interactive finish tagging
    st.subheader("📋 Pitch-Level Finish Tagging")
    for i in range(len(df_filtered)):
        col1, col2, col3, col4, col5 = st.columns([2, 2, 2, 2, 1])
        with col1:
            st.text(df_filtered.loc[i, 'Pitcher'])
        with col2:
            st.text(df_filtered.loc[i, 'TaggedPitchType'])
        with col3:
            st.text(f"H: {df_filtered.loc[i, 'PlateLocHeightInches']:.1f}")
        with col4:
            st.text(f"S: {df_filtered.loc[i, 'PlateLocSideInches']:.1f}")
        with col5:
            st.session_state.finish_flags[i] = st.checkbox("Finish", value=st.session_state.finish_flags[i], key=f"finish_{i}")

    df_filtered['IsFinish'] = st.session_state.finish_flags

    # Scoring logic
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
        in_zone = ZONE_BOTTOM <= height <= ZONE_TOP
        buffer_zone = False

        if is_fb:
            if in_zone:
                score += 2 if height > (ZONE_BOTTOM + ZONE_TOP) / 2 else 1
            elif ZONE_TOP < height <= FB_BUFFER_TOP:
                score += 1
                buffer_zone = True
        else:
            if in_zone:
                score += 2 if height < (ZONE_BOTTOM + ZONE_TOP) / 2 else 1
            elif NFB_BUFFER_BOTTOM <= height < ZONE_BOTTOM:
                score += 1
                buffer_zone = True

        # Apply finish multiplier to buffer zone point
        if is_finish and buffer_zone:
            score += 1  # Add 1 more point for x2 multiplier on buffer zone contribution

        return score

    df_filtered['PitchScore'] = df_filtered.apply(score_pitch, axis=1)

    # Pitcher filter
    selected_pitcher = st.selectbox("🎯 Filter pitches by pitcher", ["All"] + sorted(df_filtered['Pitcher'].unique().tolist()))
    if selected_pitcher != "All":
        view_df = df_filtered[df_filtered['Pitcher'] == selected_pitcher]
    else:
        view_df = df_filtered

    st.subheader("📊 Pitch-Level Data")
    st.dataframe(view_df[['Pitcher', 'TaggedPitchType', 'PlateLocHeightInches', 'PlateLocSideInches', 'IsFinish', 'PitchScore']])

    # Pitcher Summary
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

    # Download buttons
    st.download_button("📅 Download Pitch-Level Data", data=df_filtered.to_csv(index=False), file_name="pitch_data.csv", mime="text/csv")
    st.download_button("📅 Download Pitcher Summary", data=summary.to_csv(index=False), file_name="pitcher_summary.csv", mime="text/csv")

    # Visualization
    st.subheader("🎯 Strike Zone Plot")

    if selected_pitcher == "All":
        st.info("Select a specific pitcher to view their strike zone plot.")
    else:
        fig, ax = plt.subplots(figsize=(5, 6))

        shapes = {
            0: "X",
            1: "o",
            2: "o",
            3: "$",
            4: "$"
        }

        pitcher_df = view_df.copy()
        for _, row in pitcher_df.iterrows():
            color = "red" if row['IsFastball'] else "blue"
            score = row['PitchScore']
            shape = shapes.get(score, "X")

            if shape == "o" and score == 2:
                ax.plot(row['PlateLocSideInches'], row['PlateLocHeightInches'], marker='o', color=color, markersize=15)
            elif shape == "$":
                ax.text(row['PlateLocSideInches'], row['PlateLocHeightInches'], "$", color=color, fontsize=12, ha='center', va='center')
            else:
                ax.text(row['PlateLocSideInches'], row['PlateLocHeightInches'], shape, color=color, fontsize=10, ha='center', va='center')

        ax.add_patch(plt.Rectangle((ZONE_SIDE_LEFT, ZONE_BOTTOM), ZONE_SIDE_RIGHT - ZONE_SIDE_LEFT, ZONE_TOP - ZONE_BOTTOM,
                                   edgecolor='black', fill=False, linewidth=2))
        ax.set_xlim(-8.5, 8.5)
        ax.set_ylim(19.4, 38.5)
        ax.set_xlabel("Plate Side (in)")
        ax.set_ylabel("Plate Height (in)")
        ax.set_title(f"{selected_pitcher} Strike Zone")
        ax.grid(True, linestyle='--', alpha=0.5)
        st.pyplot(fig)
