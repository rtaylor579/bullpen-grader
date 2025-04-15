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

uploaded_file = st.file_uploader("Upload your bullpen CSV", type=["csv"])

if uploaded_file is not None:
    df = pd.read_csv(uploaded_file)
    st.write("### Raw Data Preview", df.head())

    pitchers = df["Pitcher"].unique()
    st.write("### Pitcher Count Designations")

    # Build form for count designation
    attack_counts = set()
    finish_counts = set()

    with st.form("count_designation_form"):
        for pitcher in pitchers:
            st.markdown(f"**{pitcher}**")
            col1, col2 = st.columns(2)
            with col1:
                if st.checkbox(f"Attack Count: {pitcher}", key=f"attack_{pitcher}"):
                    attack_counts.add(pitcher)
            with col2:
                if st.checkbox(f"Finish Count: {pitcher}", key=f"finish_{pitcher}"):
                    finish_counts.add(pitcher)

        submitted = st.form_submit_button("Submit Count Designations")

    if submitted:
        st.success("Count designations submitted!")
        st.write("### 🧠 Grading with Designations")

        # Call your grading logic function here and pass in:
        # - df (pitch data)
        # - attack_counts (set of pitcher names)
        # - finish_counts (set of pitcher names)

        # Placeholder for your scoring logic
        st.info(f"Attack Pitchers: {attack_counts}")
        st.info(f"Finish Pitchers: {finish_counts}")

        # Your final grades could be displayed below this line

