import streamlit as st
import pandas as pd

# Braves theme styling
st.markdown(
    """
    <style>
        body { background-color: #002855; color: white; }
        .stApp { background-color: #002855; }
    </style>
    """,
    unsafe_allow_html=True
)

st.title("🔥 Braves Bullpen Grader")

# Upload CSV
uploaded_file = st.file_uploader("Upload your bullpen CSV", type=["csv"])

if uploaded_file is not None:
    df = pd.read_csv(uploaded_file)
    st.write("### 🧾 Raw Data Preview", df.head())

    # Pitcher summary
    pitcher_summary = df["Pitcher"].value_counts().reset_index()
    pitcher_summary.columns = ["Pitcher", "Total Pitches"]
    pitcher_summary["Total Score"] = ""  # Placeholder for now

    st.write("### 💡 Pitcher Summary")
    st.dataframe(pitcher_summary)

    # Count Designation Section
    st.write("### 🎯 Count Designation")

    pitchers = df["Pitcher"].unique()
    attack_counts = set()
    finish_counts = set()

    with st.form("count_designation_form"):
        for pitcher in pitchers:
            st.markdown(f"**{pitcher}**")
            col1, col2 = st.columns(2)
            with col1:
                if st.checkbox(f"Attack Count", key=f"attack_{pitcher}"):
                    attack_counts.add(pitcher)
            with col2:
                if st.checkbox(f"Finish Count", key=f"finish_{pitcher}"):
                    finish_counts.add(pitcher)

        submitted = st.form_submit_button("Submit Count Designations")

    if submitted:
        st.success("✅ Count designations submitted!")
        st.write("### 🧠 Grading with Designations")

        # Replace this with your custom scoring logic
        st.info(f"Attack Pitchers: {', '.join(attack_counts) if attack_counts else 'None'}")
        st.info(f"Finish Pitchers: {', '.join(finish_counts) if finish_counts else 'None'}")

        # If you have a grading function, call it here like:
        # scores = grade_bullpen(df, attack_counts, finish_counts)
        # st.dataframe(scores)
