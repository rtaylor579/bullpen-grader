import io
import re
import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.patches as patches
from matplotlib.lines import Line2D
from matplotlib.ticker import NullLocator
from datetime import date
import requests
import json

# ── Constants ──
SUPABASE_URL = "https://rmdfrysjyzzmkjsxjchy.supabase.co"
SUPABASE_SERVICE_ROLE_KEY = (
    "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9."
    "eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InJtZGZyeXNqeXp6bWtqc3hqY2h5Iiwicm9sZ"
    "SI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc0NDkxNjE0NSwiZXhwIjoyMDYwNDkyMTQ1fQ."
    "xbP8Owj-Bz0N1KjhjkXvvnJhvbp5OzCNvJOb7-BCFhA"
)
headers = {
    "apikey": SUPABASE_SERVICE_ROLE_KEY,
    "Authorization": f"Bearer {SUPABASE_SERVICE_ROLE_KEY}",
    "Content-Type": "application/json",
}

# Strike Zone
ZONE_BOTTOM       = 19.4
ZONE_TOP          = 38.5
FB_BUFFER_TOP     = 40.5
NFB_BUFFER_BOTTOM = 17.4
ZONE_SIDE_LEFT    = -8.5
ZONE_SIDE_RIGHT   = 8.5
fastballs         = ["Fastball", "Sinker", "Cutter"]

# ── Streamlit Styling ──
PRIMARY_COLOR   = "#CE1141"
SECONDARY_COLOR = "#13274F"
BG_COLOR        = "#F5F5F5"
st.set_page_config(page_title="✏️ Bullpen Grader", layout="wide")
st.markdown(f"""
    <style>
    .main {{ background-color: {BG_COLOR}; }}
    .stButton > button {{ background-color: {PRIMARY_COLOR}; color: white; font-weight: bold; }}
    .stFileUploader, .stDataFrame {{ background-color: white; }}
    </style>
""", unsafe_allow_html=True)

# ── Sidebar ──
page = st.sidebar.radio("Go to:", [
    "➕ Upload New Session",
    "📖 View Past Sessions",
    "📈 Historical Trends"
])

# ── Helpers ──
def score_pitch(row):
    h, s = row['PlateLocHeightInches'], row['PlateLocSideInches']
    is_fb, is_fin = row['IsFastball'], row['IsFinish']
    if pd.isna(h) or pd.isna(s): return 0
    if not (ZONE_SIDE_LEFT <= s <= ZONE_SIDE_RIGHT): return 0

    score = 0
    buffer_zone = False
    mid = (ZONE_TOP + ZONE_BOTTOM) / 2
    if is_fb:
        if ZONE_BOTTOM <= h <= ZONE_TOP:
            score += 2 if h > mid else 1
        elif ZONE_TOP < h <= FB_BUFFER_TOP:
            score += 1; buffer_zone = True
    else:
        if ZONE_BOTTOM <= h <= ZONE_TOP:
            score += 2 if h < mid else 1
        elif NFB_BUFFER_BOTTOM <= h < ZONE_BOTTOM:
            score += 1; buffer_zone = True
    if is_fin and buffer_zone:
        score += 1
    return score

def letter_grade(pct):
    if pct > 0.8: return "A"
    if pct > 0.65: return "B"
    if pct > 0.5: return "C"
    if pct > 0.35: return "D"
    return "F"

# ── Pages ── #

if page == "➕ Upload New Session":
    st.title("🪓 Braves Bullpen Grader")
    st.markdown("Upload your bullpen CSV to grade and store pitches in the database.")

    uploaded_file = st.file_uploader("Upload bullpen session CSV", type=["csv"])
    if uploaded_file:
        df = pd.read_csv(uploaded_file)
        fname = uploaded_file.name
        m = re.search(r'(\d{4}-\d{2}-\d{2})', fname)
        session_date = m.group(1) if m else date.today().isoformat()

        # prepare DataFrame
        df_filtered = df[['Pitcher','TaggedPitchType','PlateLocHeight','PlateLocSide','Flag']].copy()
        df_filtered['PlateLocHeightInches'] = df_filtered['PlateLocHeight'] * 12
        df_filtered['PlateLocSideInches']   = df_filtered['PlateLocSide'] * 12
        df_filtered['IsFastball'] = df_filtered['TaggedPitchType'].str.contains(
            '|'.join(fastballs), case=False, regex=True
        )
        df_filtered['IsFinish'] = df_filtered['Flag'].astype(str).str.upper() == 'Y'
        df_filtered['PitchScore'] = df_filtered.apply(score_pitch, axis=1)
        
        # ── DROP any pitches with missing location ──
        before_count = len(df_filtered)
        df_filtered = df_filtered.dropna(
            subset=['PlateLocHeightInches','PlateLocSideInches']
       )
        dropped = before_count - len(df_filtered)
        if dropped > 0:
           st.warning(f"⚠️ Dropped {dropped} pitches with missing location data.")

        # bulk-insert raw pitches
        records = df_filtered.rename(columns={
            'Pitcher':'pitcher_name',
            'TaggedPitchType':'tagged_pitch_type',
            'PlateLocHeightInches':'plate_loc_height_inches',
            'PlateLocSideInches':'plate_loc_side_inches',
            'IsFastball':'is_fastball',
            'IsFinish':'is_finish',
            'PitchScore':'pitch_score'
        })[[
            'pitcher_name','tagged_pitch_type',
            'plate_loc_height_inches','plate_loc_side_inches',
            'is_fastball','is_finish','pitch_score'
        ]]
        records['session_date'] = session_date

        # JSON-safe conversion
        payload = json.loads(records.to_json(orient='records', date_format='iso'))

        resp = requests.post(
            f"{SUPABASE_URL}/rest/v1/pitches",
            headers=headers,
            json=payload
        )
        if resp.status_code not in (200,201):
            st.error(f"⚠️ Failed to save pitches: {resp.text}")
        else:
            st.success("✅ Stored pitches to database!")

            # summarise & insert session row
            summary = (
                df_filtered
                .groupby('Pitcher')['PitchScore']
                .agg(avg_score='mean', ppp=lambda s: s.sum() / len(s))
                .reset_index()
                .rename(columns={'Pitcher':'pitcher_name'})
            )
            summary['session_date'] = session_date

            summary_payload = json.loads(summary.to_json(orient='records', date_format='iso'))
            resp2 = requests.post(
                f"{SUPABASE_URL}/rest/v1/pitcher_sessions",
                headers=headers,
                json=summary_payload
            )
            if resp2.status_code not in (200,201):
                st.error(f"⚠️ Failed to save session summary ({resp2.status_code}): {resp2.text}")
            else:
                st.success("✅ Session summary saved!")

        # UI: show pitches & scatter
        sel = st.selectbox("🎯 Filter by pitcher",
                          ["All"] + sorted(df_filtered['Pitcher'].unique().tolist()))
        view_df = df_filtered if sel=="All" else df_filtered[df_filtered['Pitcher']==sel]
        st.subheader("📊 Pitch-Level Data")
        st.dataframe(view_df[[
            'Pitcher','TaggedPitchType',
            'PlateLocHeightInches','PlateLocSideInches',
            'IsFinish','PitchScore'
        ]])
        if sel!="All":
            fig, ax = plt.subplots(figsize=(6,8))
            for _, r in view_df.iterrows():
                x,y = r['PlateLocSideInches'], r['PlateLocHeightInches']
                sc, fb, fin = r['PitchScore'], r['IsFastball'], r['IsFinish']
                buf_fb = fb and ZONE_TOP < y <= FB_BUFFER_TOP
                buf_nf = not fb and NFB_BUFFER_BOTTOM <= y < ZONE_BOTTOM
                if sc>=3 and fin and (buf_fb or buf_nf):
                    ax.plot(x,y,marker='s',color='green',markersize=14)
                elif sc==0:
                    ax.text(x,y,"X",color='red' if fb else 'blue',ha='center',va='center')
                elif sc==1:
                    ax.plot(x,y,marker='o',color=('red' if fb else 'blue'),
                            markersize=10,markerfacecolor='none')
                else:
                    ax.plot(x,y,marker='o',color=('red' if fb else 'blue'),markersize=14)
            ax.add_patch(patches.Rectangle(
                (ZONE_SIDE_LEFT,ZONE_BOTTOM),
                ZONE_SIDE_RIGHT-ZONE_SIDE_LEFT,ZONE_TOP-ZONE_BOTTOM,
                fill=False,edgecolor='black',linewidth=2
            ))
            ax.set_xlim(-10,10); ax.set_ylim(18,42)
            ax.set_xlabel("Side (in)"); ax.set_ylabel("Height (in)")
            ax.set_title(f"{sel} Strike Zone")
            st.pyplot(fig)

# View Past Sessions
elif page == "📖 View Past Sessions":
    st.title("📖 Past Pitcher Sessions")
    if st.button("🔄 Load Past Sessions"):
        r = requests.get(f"{SUPABASE_URL}/rest/v1/pitcher_sessions?select=*", headers=headers)
        if r.status_code == 200:
            df_p = pd.DataFrame(r.json())
            st.dataframe(df_p)
        else:
            st.error("Failed to load sessions"); st.write(r.status_code, r.text)

elif page == "📈 Historical Trends":
    st.title("📈 Player Dashboard")

    # 1) Load *all* raw pitches and parse dates
    resp = requests.get(
        f"{SUPABASE_URL}/rest/v1/pitches?select=pitcher_name,session_date,pitch_score,"
        "plate_loc_side_inches,plate_loc_height_inches",
        headers=headers
    )
    if resp.status_code != 200:
        st.error("Failed to load raw pitches"); st.stop()
    df = pd.DataFrame(resp.json())
    if df.empty:
        st.info("No sessions yet. Upload a CSV first!"); st.stop()

    df['session_date'] = pd.to_datetime(df['session_date']).dt.date

    # 2) Build session summaries on the fly
    sessions = (
        df
        .groupby(['pitcher_name', 'session_date'])['pitch_score']
        .agg(ppp=lambda s: s.sum() / len(s))
        .reset_index()
    )

    # 3) Player + separate date controls
    player = st.selectbox("🎯 Select Player", sorted(sessions['pitcher_name'].unique()))
    dmin, dmax = sessions['session_date'].min(), sessions['session_date'].max()
    
    start_date = st.date_input(
        "📅 Start date",
        value=dmin, min_value=dmin, max_value=dmax
    )
    end_date = st.date_input(
        "📅 End date",
        value=dmax, min_value=dmin, max_value=dmax
    )
    # 4) Pitch‑type & mode controls
    pitch_choices = ["All","FB","SI","CH","SPL","CB","NFB"]
    sel_types    = st.multiselect("⚾ Pitch Types", pitch_choices, default=["All"])
    mode         = st.radio("🔥 Heatmap mode", ["Density","Quality"])

    # 5) Filter sessions for the PPP plot
    player_sess = sessions[
        (sessions['pitcher_name'] == player) &
        (sessions['session_date'].between(start_date, end_date))
    ].sort_values('session_date')

from matplotlib.ticker import NullLocator

col1, col2 = st.columns(2)
with col1:
    fig, ax = plt.subplots(figsize=(6,4))

    # Numeric x positions
    xs = list(range(len(player_sess)))
    ys = player_sess['ppp'].tolist()

    # Manually format each session_date to YYYY-MM-DD
    dates = [
        d.strftime("%Y-%m-%d") if hasattr(d, "strftime") else str(d)
        for d in player_sess['session_date']
    ]

    # Color mapping
    colors = {"A":"green","B":"blue","C":"orange","D":"purple","F":"red"}

    # Plot & annotate
    for i, v in zip(xs, ys):
        g = letter_grade(v)
        ax.scatter(i, v, color=colors[g], s=100)
        ax.text(i + 0.05, v + 0.005, g, ha='left', va='center')

    # Set custom ticks & labels
    ax.set_xticks(xs)
    ax.set_xticklabels(dates, rotation=45, ha='right')

    # Disable minor ticks (prevents Matplotlib errors)
    ax.xaxis.set_minor_locator(NullLocator())
    ax.minorticks_off()

    ax.set_xlabel("Date")
    ax.set_ylabel("Points Per Pitch")
    ax.set_title(f"{player} — PPP Trend")
    st.pyplot(fig)


    # 7) Now filter the same raw df for the heatmap
    mask = (
        (df['pitcher_name'] == player) &
        (df['session_date'] >= start_date) &
        (df['session_date'] <= end_date)
    )
    if "All" not in sel_types:
        type_map = {"FB":"^4S$","SI":"(Sinker|2S)","CH":"ChangeUp","SPL":"Splitter","CB":"Curve"}
        if "NFB" in sel_types:
            fb_re = "|".join([type_map["FB"], type_map["SI"]])
            mask &= ~df['tagged_pitch_type'].str.contains(fb_re, case=False, regex=True)
        else:
            regex = "|".join(type_map[t] for t in sel_types if t in type_map)
            mask &= df['tagged_pitch_type'].str.contains(regex, case=False, regex=True)

    pitches = df[mask]
    if pitches.empty:
        st.warning("No pitches in that selection."); st.stop()

    # 8) Draw the hex‑bin heatmap
    with col2:
        fig2, ax2 = plt.subplots(figsize=(6,6))
        x = pitches['plate_loc_side_inches']
        y = pitches['plate_loc_height_inches']
        if mode == "Density":
            hb = ax2.hexbin(x, y, gridsize=20, mincnt=1)
            fig2.colorbar(hb, ax=ax2, label="Count")
        else:
            hb = ax2.hexbin(x, y, C=pitches['pitch_score'],
                            reduce_C_function=np.mean,
                            gridsize=20, mincnt=1)
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
