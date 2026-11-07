import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from streamlit_sortables import sort_items
from datetime import datetime, timedelta
import pytz
from collections import defaultdict

st.set_page_config(page_title="Associated Goys Top 25 Poll", layout="wide")

st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Bebas+Neue&display=swap');

    html, body, [class*="css"] {
        font-family: 'Bebas Neue', sans-serif !important;
        letter-spacing: 2px !important;
    }
    h1, h2, h3, h4, h5, h6, .stSubheader, .stMarkdown, button, .stButton > button, .stTextInput label, .stTextInput input {
        font-family: 'Bebas Neue', sans-serif !important;
        letter-spacing: 2px !important;
    }

    .block-container { 
        padding-top: 1.5rem !important; 
        padding-bottom: 0.5rem !important; 
    }
    h1 { 
        font-size: 2rem !important; 
        margin-bottom: 0.6rem !important; 
        margin-top: 0.5rem !important;
        text-align: center !important;
    }
    h2, h3 { 
        font-size: 1.15rem !important; 
        margin: 0.3rem 0 !important; 
        text-align: center !important; 
    }
    button[data-baseweb="tab"] { font-size: 1.05rem !important; font-weight: 600 !important; padding: 0.4rem 1rem !important; }
    button[data-baseweb="tab"][aria-selected="true"],
    button[data-baseweb="tab"]:hover { background-color: #D4AF37 !important; color: #1a1a1a !important; }
    .stButton > button, button[kind="primary"] {
        background-color: #D4AF37 !important; 
        color: #1a1a1a !important; 
        border: none !important;
        text-align: left !important;
        padding: 7px 12px !important;
        margin: 2px 0 !important;
        border-radius: 5px !important;
        font-size: 0.95rem !important;
        font-weight: 700 !important;
        width: 100% !important;
        font-family: 'Bebas Neue', sans-serif !important;
        letter-spacing: 2px !important;
    }
    .stButton > button:hover, button[kind="primary"]:hover { background-color: #E6C200 !important; }

    .center-header {
        font-size: 1.45rem !important;
        margin: 0.2rem 0 0.4rem 0 !important;
        text-align: center !important;
    }
</style>
""", unsafe_allow_html=True)

CENTER_STYLE = """
.sortable-container {
    background: transparent !important;
}
.sortable-container-body {
    background: transparent !important;
    max-height: 680px !important;
    min-height: 680px !important;
    overflow-y: hidden !important;
}
.sortable-item {
    background-color: #4CAF50 !important;
    color: #1a1a1a !important;
    text-align: left !important;
    padding: 3px 10px !important;
    margin: 1px 0 !important;
    border-radius: 4px !important;
    font-size: 0.9rem !important;
    line-height: 1.25 !important;
    min-height: 22px !important;
    font-family: 'Bebas Neue', sans-serif !important;
    letter-spacing: 2px !important;
    font-weight: 700 !important;
}
.sortable-item:hover { background-color: #66BB6A !important; }
"""

ET = pytz.timezone("America/New_York")

def get_current_week_range():
    now = datetime.now(ET)
    days_since_monday = now.weekday()
    monday = (now - timedelta(days=days_since_monday)).replace(hour=0, minute=0, second=0, microsecond=0)
    sunday = monday + timedelta(days=6)
    sunday = sunday.replace(hour=23, minute=59, second=59)
    return monday, sunday

def format_date_range():
    monday, sunday = get_current_week_range()
    def ordinal(n):
        if 11 <= n % 100 <= 13:
            suffix = "th"
        else:
            suffix = {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
        return f"{n}{suffix}"
    def fmt(d):
        return f"{d.strftime('%B')} {ordinal(d.day)}, '{d.strftime('%y')}"
    return f"{fmt(monday)} - {fmt(sunday)}"

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

@st.cache_resource
def get_gsheet_client():
    creds = Credentials.from_service_account_info(
        st.secrets["gcp_service_account"], scopes=SCOPES
    )
    return gspread.authorize(creds)

def is_open():
    now = datetime.now(ET)
    return not (now.weekday() == 6 and now.hour == 23 and now.minute >= 59)

@st.cache_data
def load_teams():
    try:
        df = pd.read_csv("teams.csv")
        return df["Team"].dropna().astype(str).str.strip().tolist()
    except Exception as e:
        st.error(f"Could not load teams.csv: {e}")
        return []

def open_sheet(gc):
    try:
        return gc.open_by_url(st.secrets["gsheets"]["spreadsheet_url"])
    except Exception as e:
        st.error(f"Could not open Google Sheet: {type(e).__name__}")
        st.code(str(e))
        return None

def save_submission(gc, person, ranking):
    sh = open_sheet(gc)
    if not sh:
        return False
    try:
        ws = sh.worksheet("Submissions")
        records = ws.get_all_records()
        row_num = None
        for i, rec in enumerate(records, start=2):
            if rec.get("Person") == person:
                row_num = i
                break
        timestamp = datetime.now(ET).strftime("%Y-%m-%d %H:%M:%S")
        row_data = [timestamp, person] + ranking + [""] * (25 - len(ranking))
        if row_num:
            ws.update(f"A{row_num}:Z{row_num}", [row_data])
        else:
            ws.append_row(row_data)
        st.cache_data.clear()
        return True
    except Exception as e:
        st.error(f"Save failed: {e}")
        return False

@st.cache_data(ttl=30)
def load_results(_gc):
    sh = open_sheet(_gc)
    if not sh:
        return pd.DataFrame()
    try:
        ws = sh.worksheet("Submissions")
        data = ws.get_all_records()
        if not data:
            return pd.DataFrame()
        df = pd.DataFrame(data)
        df["Timestamp"] = pd.to_datetime(df["Timestamp"])
        latest = df.sort_values("Timestamp").groupby("Person").tail(1)

        try:
            weights_df = pd.DataFrame(sh.worksheet("Weights").get_all_records())
        except Exception:
            weights_df = pd.DataFrame()

        points = defaultdict(float)
        firsts = defaultdict(int)
        for _, row in latest.iterrows():
            person = row["Person"]
            w = 1.0
            if not weights_df.empty and "Person" in weights_df.columns and person in weights_df["Person"].values:
                w = float(weights_df.loc[weights_df["Person"] == person, "Weight"].iloc[0])
            for pos in range(1, 26):
                team = row.get(f"Rank{pos}")
                if team:
                    points[team] += (26 - pos) * w
                    if pos == 1:
                        firsts[team] += 1
        results = [{"Team": t, "Points": round(p, 2), "First Place Votes": firsts[t]}
                   for t, p in points.items()]
        results.sort(key=lambda x: (-x["Points"], -x["First Place Votes"]))
        return pd.DataFrame(results)
    except Exception as e:
        st.error(f"Could not load results: {e}")
        return pd.DataFrame()

# --- UI ---
date_range = format_date_range()
st.title(f"Associated Goys Top 25 Poll | {date_range}")

gc = get_gsheet_client()
teams = load_teams()

tab1, tab2 = st.tabs(["Submit Rankings", "Current Results"])

with tab1:
    if not is_open():
        st.error("Submissions are closed until next week (cutoff is Sunday 11:59 PM ET).")
    else:
        person = st.text_input("Your name (used to identify & overwrite your ballot)")
        if person:
            if "ranking" not in st.session_state:
                st.session_state.ranking = []

            col_left, col_center, col_right = st.columns([1, 2, 1])

            with col_left:
                st.subheader("Available Teams (click to add)")
                available = [t for t in teams if t not in st.session_state.ranking]
                with st.container(height=680):
                    for team in available:
                        if st.button(team, key=f"add_{team}", use_container_width=True):
                            if len(st.session_state.ranking) < 25:
                                st.session_state.ranking.append(team)
                                st.rerun()

            with col_center:
                display_name = person.strip() or "Your"
                st.markdown(f'<h3 class="center-header">{display_name} Rankings (drag to reorder)</h3>', unsafe_allow_html=True)
                
                numbered = [f"{i+1}. {team}" for i, team in enumerate(st.session_state.ranking)]
                
                # More stable key reduces full remounts
                center_result = sort_items(
                    numbered,
                    direction="vertical",
                    key="ranking_sortable",
                    custom_style=CENTER_STYLE
                )
                
                new_ranking = [item.split(". ", 1)[1] if ". " in item else item for item in center_result]
                
                # Only update + rerun if the order actually changed
                if new_ranking != st.session_state.ranking and len(new_ranking) == len(st.session_state.ranking):
                    st.session_state.ranking = new_ranking
                    st.rerun()

            with col_right:
                st.subheader("Submit")
                if st.session_state.ranking:
                    if st.button("Submit / Update Ranking", type="primary", use_container_width=True):
                        if save_submission(gc, person.strip(), st.session_state.ranking):
                            st.success("Ranking saved.")
                            st.session_state.ranking = []
                            st.rerun()
                else:
                    st.button("Submit / Update Ranking", disabled=True, use_container_width=True)

with tab2:
    st.subheader("Weighted Aggregate Top 25")
    if st.button("Refresh Results"):
        st.cache_data.clear()
    results = load_results(gc)
    if not results.empty:
        st.dataframe(results.head(25), use_container_width=True)
        st.caption("Weights come from the Weights tab. Edit them anytime.")
    else:
        st.info("No submissions yet (or sheet temporarily unavailable).")
