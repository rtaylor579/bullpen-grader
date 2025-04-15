import streamlit as st
import pandas as pd

# Braves theme styling
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

uploaded_file = st.file_uploader("Upload your bullpen CSV", type=["csv"])

if uploaded_file is not None:
    df = pd.read_csv(uploaded_file)
    st.write("### Raw Data Preview", df.head())

    pitchers = df["Pitcher"].unique()
    
    # Pitcher summary
    pitcher_summary = df["Pitcher"].value_counts().reset_index()
    pitcher_summary.columns = ["Pitcher", "Total Pitches"]
    pitcher_summary["Total Score"] = ""  # Placeholder
    st.write("### 🧢 Pitcher Summary")
    st.dataframe(pitcher_summary)

    st.write("### 🎯 Count Designation")

    # Create form for Attack / Finish designation
    with st.form("count_form"):
        st.write("Select count designation for each pitcher:")
        attack_counts = []
        finish_counts = []
        
        for pitcher in pitchers:
            st.write(f"**{pitcher}**")
            col1, col2 = st.columns(2)
            with col1:
                is_attack = st.checkbox(f"Attack", key=f"attack_{pitcher}")
            with col2:
                is_finish = st.checkbox(f"Finish", key=f"finish_{pitcher}")
            
            if is_attack:
                attack_counts.append(pitcher)
            if is_finish:
                finish_counts.append(pitcher)

        submitted = st.form_submit_button("Submit Count Designations")

    if submitted:
        st.success("✅ Designations saved!")
        st.write("### 🧠 Grading with Designations")
        st.write(f"**Attack Pitchers:** {', '.join(attack_counts) if attack_counts else 'None'}")
        st.write(f"**Finish Pitchers:** {', '.join(finish_counts) if finish_counts else 'None'}")

        # You can now pass these into your grading function
        # grades = grade_bullpen(df, attack_counts, finish_counts)
        # st.dataframe(grades)

else:
    st.info("Please upload a CSV file to get started.")

