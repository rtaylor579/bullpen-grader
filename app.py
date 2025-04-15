import streamlit as st
import pandas as pd

st.set_page_config(layout="wide")

st.markdown(
    """
    <style>
        body { background-color: #002855; color: white; }
        .stApp { background-color: #002855; color: white; }
    </style>
    """,
    unsafe_allow_html=True
)

st.title("🔥 Braves Bullpen Grader")

# Upload CSV
uploaded_file = st.file_uploader("Upload your bullpen CSV", type=["csv"])

if uploaded_file is not None:
    df = pd.read_csv(uploaded_file)

    # Preview
    st.subheader("🔍 Raw Data Preview")
    st.dataframe(df.head(), use_container_width=True)

    # Create checkbox columns for attack/finish designation
    st.subheader("⚔️ Tag Each Pitch as Attack or Finish")
    with st.form("pitch_designation_form"):
        attack_flags = []
        finish_flags = []

        for idx, row in df.iterrows():
            col1, col2, col3 = st.columns([3, 1, 1])
            with col1:
                st.write(f"{row['Pitcher']} - {row['TaggedPitchType']} | Zone Height: {row['ZoneLocHeight']}, Side: {row['ZoneLocSide']}")
            with col2:
                attack = st.checkbox("Attack", key=f"attack_{idx}")
            with col3:
                finish = st.checkbox("Finish", key=f"finish_{idx}")
            attack_flags.append(attack)
            finish_flags.append(finish)

        submit = st.form_submit_button("Submit Designations")

    if submit:
        df["Attack"] = attack_flags
        df["Finish"] = finish_flags
        st.success("Designations added to each pitch!")

        # Grading logic
        def score_pitch(row):
            fb_types = ["Fastball", "4-Seam", "Four-Seam"]
            is_fb = row["TaggedPitchType"] in fb_types

            score = 0
            if is_fb:
                if row["ZoneLocHeight"] > 0.5:
                    score += 2  # Upper zone FB
                elif 0.4 < row["ZoneLocHeight"] <= 0.5:
                    score += 1  # Buffer zone FB
            else:
                if row["ZoneLocHeight"] < 0.4:
                    score += 2  # Lower zone NFB
                elif 0.4 <= row["ZoneLocHeight"] < 0.5:
                    score += 1  # Buffer zone NFB

            # Optional bonuses
            if row.get("Attack"):
                score += 1
            if row.get("Finish"):
                score += 1

            return score

        df["Score"] = df.apply(score_pitch, axis=1)

        # Show full table with scores
        st.subheader("📊 Graded Pitches")
        st.dataframe(df, use_container_width=True)

        # Pitcher Summary
        st.subheader("📋 Pitcher Summary")
        summary = df.groupby("Pitcher").agg(
            Total_Pitches=pd.NamedAgg(column="TaggedPitchType", aggfunc="count"),
            Total_Score=pd.NamedAgg(column="Score", aggfunc="sum")
        ).reset_index()

        st.dataframe(summary, use_container_width=True)
