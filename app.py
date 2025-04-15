import streamlit as st
import pandas as pd

# Braves color theme
PRIMARY_COLOR = "#CE1141"  # Braves red
SECONDARY_COLOR = "#13274F"  # Braves navy
BG_COLOR = "#F5F5F5"  # Light background

st.set_page_config(page_title="Bullpen Grader", layout="wide")

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

st.title("🔥 Braves Bullpen Grader")
st.markdown("Upload your bullpen CSV and get instant grading feedback.")

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

    df_filtered['IsFastball'] = df_filtered['TaggedPitchType'].str.contains('Fastball', case=False, na=False)

    def score_pitch(row):
        height = row['PlateLocHeightInches']
        side = row['PlateLocSideInches']

        if pd.isnull(height) or pd.isnull(side):
            return 0
        if not (ZONE_SIDE_LEFT <= side <= ZONE_SIDE_RIGHT):
            return 0

        if row['IsFastball']:
            if ZONE_BOTTOM <= height <= ZONE_TOP:
                return 2 if height > (ZONE_BOTTOM + ZONE_TOP) / 2 else 1
            elif ZONE_TOP < height <= FB_BUFFER_TOP:
                return 1
        else:
            if ZONE_BOTTOM <= height <= ZONE_TOP:
                return 2 if height < (ZONE_BOTTOM + ZONE_TOP) / 2 else 1
            elif NFB_BUFFER_BOTTOM <= height < ZONE_BOTTOM:
                return 1
        return 0

    df_filtered['PitchScore'] = df_filtered.apply(score_pitch, axis=1)

    # Pitch summary
    st.subheader("📋 Pitch-Level Results")
    st.dataframe(df_filtered[['Pitcher', 'TaggedPitchType', 'PlateLocHeightInches', 'PlateLocSideInches', 'PitchScore']])

    # Pitcher summary
    pitcher_scores = df_filtered.groupby('Pitcher')['PitchScore'].agg(['count', 'sum']).reset_index()
    pitcher_scores.columns = ['Pitcher', 'Total Pitches', 'Total Score']

    st.subheader("🧢 Pitcher Summary")
    st.dataframe(pitcher_scores)

    # Placeholder for upcoming Count Designation UI
    st.subheader("⚙️ Count Designation (Coming Next)")
    st.markdown("Soon you'll be able to tag pitchers as being in Attack or Finish counts for custom scoring adjustments.")
