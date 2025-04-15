import streamlit as st
import pandas as pd

# -------------------------------
# Braves theme styling
# -------------------------------
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

st.title("🔥 Braves Bullpen Grader")

# -------------------------------
# File uploader
# -------------------------------
uploaded_file = st.file_uploader("Upload your bullpen CSV", type=["csv"])

if uploaded_file is not None:
    df = pd.read_csv(uploaded_file)
    st.write("### 🧾 Raw Data Preview", df.head())

    st.write("### 🧪 Designate Count Type for Each Pitch")

    attack_flags = []
    finish_flags = []

    # -------------------------------
    # Interactive pitch-by-pitch form
    # -------------------------------
    with st.form("designation_form"):
        for idx, row in df.iterrows():
            col1, col2, col3 = st.columns([3, 1, 1])
            with col1:
                st.markdown(
                    f"<span style='color:white'>{row['Pitcher']} - {row['TaggedPitchType']} "
                    f"({row['ZoneLocSide']}, {row['ZoneLocHeight']:.2f})</span>",
                    unsafe_allow_html=True
                )
            with col2:
                attack = st.checkbox("Attack", key=f"attack_{idx}")
            with col3:
                finish = st.checkbox("Finish", key=f"finish_{idx}")
            attack_flags.append(attack)
            finish_flags.append(finish)

        submitted = st.form_submit_button("Submit Designations")

    if submitted:
        df["Attack"] = attack_flags
        df["Finish"] = finish_flags

        st.success("Count designations submitted!")
        st.write("### 🧠 Grading Session...")

        # -------------------------------
        # Grading Function
        # -------------------------------
        def score_pitch(row):
            fb_types = ["4-Seam", "Four-Seam", "Fastball", "4SFB"]
            is_fb = row["TaggedPitchType"] in fb_types
            height = row["ZoneLocHeight"]
            side = abs(row["ZoneLocSide"])  # center is 0, zone width is 17", so ~8.5" each direction
            score = 0

            # Strike zone constants
            bottom_zone = 19.4
            top_zone = 38.5
            left_zone = -8.5
            right_zone = 8.5
            buffer = 2.0

            # Convert from inches to normalized location if needed
            # (assuming already normalized from 0 to 1, otherwise normalize height here)

            # Height-based logic
            if is_fb:
                if height >= 0.5:
                    score += 2  # upper zone FB
                elif height > 0.385 and height < 0.5:
                    score += 1  # buffer zone FB
            else:
                if height <= 0.385:
                    score += 2  # lower zone NFB
                elif height > 0.385 and height < 0.485:
                    score += 1  # buffer zone NFB

            # Side-based logic
            if -0.425 <= row["ZoneLocSide"] <= 0.425:  # Approx. 17" zone
                score += 1
            elif -0.525 <= row["ZoneLocSide"] <= 0.525:
                score += 1  # Buffer

            # Count type bonus
            if row["Attack"]:
                score += 1
            if row["Finish"]:
                score += 1

            return score

        # -------------------------------
        # Apply scoring
        # -------------------------------
        df["Score"] = df.apply(score_pitch, axis=1)

        st.write("### 📊 Pitch-by-Pitch Scores")
        st.dataframe(df[["Pitcher", "TaggedPitchType", "ZoneLocSide", "ZoneLocHeight", "Attack", "Finish", "Score"]])

        total_score = df["Score"].sum()
        st.markdown(f"## 🧾 Total Bullpen Score: `{total_score}`")

