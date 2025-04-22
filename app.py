import io
import re
import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.patches as patches
from matplotlib.lines import Line2D
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
    mid = (ZONE_TOP + ZONE_BOTTOM)/2
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
    if pct > 0.8:  return "A"
    if pct > 0.65: return "B"
    if pct > 0.5:  return "C"
    if pct > 0.35: return "D"
    return "F"

# ── Pages ── #
# 1) Upload New Session
if page == "➕ Upload New Session":
    st.title("🪓 Braves Bullpen Grader")
    st.markdown("Upload your bullpen CSV to grade and store pitches in the database.")

    uploaded_file = st.file_uploader(
        "Upload bullpen session CSV", type=["csv"], key="upload_new_session_file"
    )
    if uploaded_file:
        df = pd.read_csv(uploaded_file)
        fname = uploaded_file.name
        m = re.search(r'(\d{4}-\d{2}-\d{2})', fname)
        session_date = m.group(1) if m else date.today().isoformat()

        # prepare DataFrame
        df_filtered = df[[
            'Pitcher','TaggedPitchType','PlateLocHeight','PlateLocSide','Flag'
        ]].copy()
        df_filtered['PlateLocHeightInches'] = df_filtered['PlateLocHeight'] * 12
        df_filtered['PlateLocSideInches']   = df_filtered['PlateLocSide']   * 12
        df_filtered['IsFastball'] = df_filtered['TaggedPitchType'].str.contains(
            '|'.join(fastballs), case=False, regex=True
        )
        df_filtered['IsFinish'] = df_filtered['Flag'].astype(str).str.upper() == 'Y'
        df_filtered['PitchScore'] = df_filtered.apply(score_pitch, axis=1)

        # bulk‑insert into Supabase
        records = df_filtered.rename(columns={
            'Pitcher':               'pitcher_name',
            'TaggedPitchType':       'tagged_pitch_type',
            'PlateLocHeightInches':  'plate_loc_height_inches',
            'PlateLocSideInches':    'plate_loc_side_inches',
            'IsFastball':            'is_fastball',
            'IsFinish':              'is_finish',
            'PitchScore':            'pitch_score'
        })[[
            'pitcher_name','tagged_pitch_type',
            'plate_loc_height_inches','plate_loc_side_inches',
            'is_fastball','is_finish','pitch_score'
        ]]
        records['session_date'] = session_date

        # convert numpy types → Python built‑ins
        records = records.applymap(
            lambda x: x.item() if isinstance(x, np.generic) else x
        )
        payload = records.to_dict(orient='records')

        resp = requests.post(
            f"{SUPABASE_URL}/rest/v1/pitches",
            headers=headers,
            json=payload
        )
        if resp.status_code not in (200,201):
            st.error("⚠️ Failed to save pitches:", resp.text)
        else:
            st.success("✅ Stored pitches to database!")


            # ── AFTER inserting raw pitches, summarize and insert session row ──

        # 1) Build a summary per pitcher
        summary = (
            df_filtered
            .groupby('Pitcher')['PitchScore']
            .agg([
                ('avg_score', 'mean'),
                ('ppp', lambda s: s.sum() / len(s))
            ])
            .reset_index()
            .rename(columns={'Pitcher':'pitcher_name'})
        )
        summary['session_date'] = session_date
        summary = summary.applymap(lambda x: x.item() if isinstance(x, np.generic) else x)

        resp2 = requests.post(
            f"{SUPABASE_URL}/rest/v1/pitcher_sessions",
            headers=headers,
            json=summary.to_dict(orient='records')
        )
        if resp2.status_code not in (200,201):
            st.error("⚠️ Failed to save session summary:", resp2.status_code, resp2.text)
        else:
            st.success("✅ Session summary saved!")


        # show raw pitch table & zone plot
        sel = st.selectbox(
            "🎯 Filter by pitcher",
            ["All"] + sorted(df_filtered['Pitcher'].unique().tolist())
        )
        view_df = df_filtered if sel=="All" else df_filtered[df_filtered['Pitcher']==sel]

        st.subheader("📊 Pitch-Level Data")
        st.dataframe(view_df[[
            'Pitcher','TaggedPitchType',
            'PlateLocHeightInches','PlateLocSideInches',
            'IsFinish','PitchScore'
        ]])

        if sel!="All":
            st.subheader("🎯 Strike Zone Plot")
            fig, ax = plt.subplots(figsize=(6,8))
            for _, row in view_df.iterrows():
                x,y = row['PlateLocSideInches'], row['PlateLocHeightInches']
                score,is_fb,is_fin = row['PitchScore'], row['IsFastball'], row['IsFinish']
                in_fb_buf = is_fb and ZONE_TOP < y <= FB_BUFFER_TOP
                in_nf_buf = not is_fb and NFB_BUFFER_BOTTOM <= y < ZONE_BOTTOM

                if score>=3 and is_fin and (in_fb_buf or in_nf_buf):
                    ax.plot(x,y,marker='s',color='green',markersize=14)
                elif score==0:
                    ax.text(x,y,"X",color='red' if is_fb else 'blue',ha='center',va='center')
                elif score==1:
                    ax.plot(x,y,marker='o',color=('red' if is_fb else 'blue'),
                            markersize=10,markerfacecolor='none')
                else:
                    ax.plot(x,y,marker='o',color=('red' if is_fb else 'blue'),markersize=14)

            # draw zone
            ax.add_patch(patches.Rectangle(
                (ZONE_SIDE_LEFT, ZONE_BOTTOM),
                ZONE_SIDE_RIGHT - ZONE_SIDE_LEFT,
                ZONE_TOP - ZONE_BOTTOM,
                fill=False,edgecolor='black',linewidth=2
            ))
            ax.set_xlim(-10,10); ax.set_ylim(18,42)
            ax.set_xlabel("Side (in)"); ax.set_ylabel("Height (in)")
            ax.set_title(f"{sel} Strike Zone")
            st.pyplot(fig)

# 2) View Past Sessions
elif page == "📖 View Past Sessions":
    st.title("📖 Past Pitcher Sessions")
    if st.button("🔄 Load Past Sessions"):
        r = requests.get(f"{SUPABASE_URL}/rest/v1/pitcher_sessions?select=*", headers=headers)
        if r.status_code == 200:
            df = pd.DataFrame(r.json())
            st.dataframe(df)
        else:
            st.error("Failed to load sessions")
            st.write(r.status_code, r.text)

# 3) Historical Trends
elif page == "📈 Historical Trends":
    st.title("📈 Player Dashboard")

    # A) load session summaries
    r = requests.get(
        f"{SUPABASE_URL}/rest/v1/pitcher_sessions?select=session_date,pitcher_name,ppp",
        headers=headers
    )
    if r.status_code != 200:
        st.error("Failed to load sessions"); st.stop()
    sessions = pd.DataFrame(r.json())
    sessions['session_date'] = pd.to_datetime(sessions['session_date']).dt.date
    if sessions.empty:
        st.info("No sessions yet."); st.stop()

    # B) controls
    player = st.selectbox("🎯 Select Player", sorted(sessions['pitcher_name'].unique()))
    dmin,dmax = sessions['session_date'].min(), sessions['session_date'].max()
    start_date,end_date = st.date_input(
        "📅 Date range", value=(dmin,dmax), min_value=dmin, max_value=dmax
    )
    pitch_choices = ["All","FB","SI","CH","SPL","CB","NFB"]
    sel_types = st.multiselect("⚾ Pitch Types", pitch_choices, default=["All"])
    mode = st.radio("🔥 Heatmap mode", ["Density","Quality"])

    # C) fetch raw pitches
    flts = [
        f"pitcher_name=eq.{player}",
        f"session_date=gte.{start_date}",
        f"session_date=lte.{end_date}"
    ]
    type_map = {
        "FB": "^4S$",
        "SI": "(Sinker|2S)",
        "CH": "ChangeUp",
        "SPL":"Splitter",
        "CB":"Curve",
        "NFB":None
    }
    if "All" not in sel_types:
        if "NFB" in sel_types:
            fb_re = "|".join([type_map["FB"],type_map["SI"]])
            flts.append(f"not(tagged_pitch_type.ilike.*{fb_re}*)")
        else:
            rex = "|".join(type_map[t] for t in sel_types)
            flts.append(f"tagged_pitch_type.ilike.*{rex}*")

    qstr = "&".join(flts)
    p = requests.get(
        f"{SUPABASE_URL}/rest/v1/pitches?select=*,pitch_score,plate_loc_side_inches,plate_loc_height_inches&{qstr}",
        headers=headers
    )
    pitches = pd.DataFrame(p.json())
    if pitches.empty:
        st.warning("No pitches in that selection."); st.stop()

    # D) layout & plots
    col1,col2 = st.columns(2)

    # D1) PPP trend + grades
    with col1:
        ps = sessions[
            (sessions['pitcher_name']==player) &
            sessions['session_date'].between(start_date,end_date)
        ].sort_values('session_date')
        fig,ax = plt.subplots(figsize=(6,4))
        xs,ys = ps['session_date'], ps['ppp']
        for d,v in zip(xs,ys):
            g = letter_grade(v)
            ax.scatter(d,v,color={
                "A":"green","B":"blue","C":"orange","D":"purple","F":"red"
            }[g],s=100)
            ax.text(d,v+0.02,g,ha='center')
        ax.set_xticks(xs); fig.autofmt_xdate()
        ax.set_xlabel("Date"); ax.set_ylabel("Points Per Pitch")
        ax.set_title(f"{player} — PPP Trend")
        st.pyplot(fig)

    # D2) strike‑zone heatmap
    with col2:
        fig2,ax2 = plt.subplots(figsize=(6,6))
        x = pitches['plate_loc_side_inches']
        y = pitches['plate_loc_height_inches']
        if mode=="Density":
            hb = ax2.hexbin(x,y,gridsize=20,mincnt=1)
            fig2.colorbar(hb,ax=ax2,label="Pitch count")
        else:
            hb = ax2.hexbin(
                x,y,
                C=pitches['pitch_score'],
                reduce_C_function=np.mean,
                gridsize=20,mincnt=1
            )
            fig2.colorbar(hb,ax=ax2,label="Avg PitchScore")
        ax2.add_patch(patches.Rectangle(
            (ZONE_SIDE_LEFT,ZONE_BOTTOM),
            ZONE_SIDE_RIGHT - ZONE_SIDE_LEFT,
            ZONE_TOP - ZONE_BOTTOM,
            fill=False,edgecolor='black',linewidth=2
        ))
        ax2.set_xlim(ZONE_SIDE_LEFT*1.2,ZONE_SIDE_RIGHT*1.2)
        ax2.set_ylim(NFB_BUFFER_BOTTOM*0.9,FB_BUFFER_TOP*1.05)
        ax2.set_xlabel("Side (in)"); ax2.set_ylabel("Height (in)")
        ax2.set_title(f"{player} — Strike‑Zone HeatMap ({mode})")
        st.pyplot(fig2)








