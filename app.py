import streamlit as st
import pandas as pd

# Braves theme styling
st.markdown(
    """
    <style>
        body { background-color: #002855; color: white; }
        .stApp { background-color: #002855; }
        .stButton>button {
            color: white;
            background-color: #CE1141;
        }
    </style>
    """,
    unsafe_allow_html=True
)

st.title(" 🪓 Braves Bullpen Grader")

# Upload CSV
uploaded_file = st.file_uploader("Upload your bullpen CSV", type=["csv"])

if uploaded_file is not None:
    df = pd.read_csv(uploaded_file)
    st.write("### 🧾 Raw Data Preview", df.head())

    # Grading Function
    def score_pitch(row):
        fb_types = ["4-Seam", "Four-Seam", "Fastball", "4SFB"]
        is_fb = row["TaggedPitchType"] in fb_types
        height = row["ZoneLocHeight"]
        side = abs(row["ZoneLocSide"])
        score = 0

        # Vertical scoring
        if is_fb:
            if height >= 0.5:
                score += 2  # FB in upper half
            elif 0.485 < height < 0.5:
                score += 1  # FB in buffer zone
        else:
            if height <= 0.385:
                score += 2  # NFB in lower half
            elif 0.385 < height < 0.405:
                score += 1  # NFB in buffer zone

        # Horizontal scoring
        if -0.425 <= row["ZoneLocSide"] <= 0.425:
            score += 1  # in zone
        elif -0.5 <= row["ZoneLocSide"] <= 0.5:
            score += 1  # buffer zone

        return score

    # Apply scoring
    df["Score"] = df.apply(score_pitch, axis=1)

    st.write("### 🎯 Graded Pitches")
    st.dataframe(df[["Pitcher", "TaggedPitchType", "ZoneLocSide", "ZoneLocHeight", "Score"]])

    total_score = df["Score"].sum()
    st.markdown(f"## 🧾 Total Bullpen Score: `{total_score}`")
