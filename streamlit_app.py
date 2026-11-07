import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from streamlit_sortables import sort_items
from datetime import datetime, timedelta
import pytz
from collections import defaultdict

st.set_page_config(page_title="Associated Goys Top 25 Poll", layout="wide")

# Tabs + buttons styling
st.markdown("""
<style>
    button[data-baseweb="tab"] {
        font-size: 1.15rem !important;
        font-weight: 600 !important;
        padding: 0.6rem 1.2rem !important;
    }
    button[data-baseweb="tab"][aria-selected="true"],
    button[data-baseweb="tab"]:hover {
        background-color: #D4AF37 !important;
        color: #1a1a1a !important;
        border-bottom: 3px solid #D4AF37 !important;
    }
    .stButton > button,
    button[kind="primary"] {
        background-color: #D4AF37 !important;
        color: #1a1a1a !important;
        border: none !important;
    }
    .stButton > button:hover,
    button[kind="primary"]:hover {
        background-color: #E6C200 !important;
    }
</style>
""", unsafe_allow_html=True)

# CSS for the sortable blocks
SORTABLE_STYLE = """
.sortable-item {
    background-color: #D4AF37 !important;
    color: #1a1a1a !important;
    text-align: left !important;
    justify-content: flex-start !important;
    padding: 10px 16px !important;
    margin: 4px 0 !important;
    border-radius: 6px !important;
    font-weight: 500;
    display: block !important;
    width: 100% !important;
}
.sortable-item:hover {
    background-color: #E6C200 !important;
}
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

            col1, col2 = st.columns(2)

            with col1:
                st.subheader("Available Teams")
                available = [t for t in teams if t not in st.session_state.ranking]
                for team in available:
                    c1, c2 = st.columns([4, 1])
                    c1.write(team)
                    if c2.button("Add", key=f"add_{team}"):
                        if len(st.session_state.ranking) < 25:
                            st.session_state.ranking.append(team)
                            st.rerun()

            with col2:
                display_name = person.strip() or "Your"
                st.subheader(f"{display_name} Rankings (drag to reorder)")

                if st.session_state.ranking:
                    numbered = [f"{i+1}. {team}" for i, team in enumerate(st.session_state.ranking)]
                    sort_key = f"rank_{len(st.session_state.ranking)}_{hash(tuple(st.session_state.ranking))}"

                    reordered_numbered = sort_items(
                        numbered,
                        direction="vertical",
                        key=sort_key,
                        custom_style=SORTABLE_STYLE
                    )

                    new_ranking = []
                    for item in reordered_numbered:
                        if ". " in item:
                            new_ranking.append(item.split(". ", 1)[1])
                        else:
                            new_ranking.append(item)

                    if new_ranking != st.session_state.ranking:
                        st.session_state.ranking = new_ranking
                        st.rerun()

                    if st.button("Submit / Update Ranking", type="primary"):
                        if save_submission(gc, person.strip(), st.session_state.ranking):
                            st.success("Ranking saved.")
                            st.session_state.ranking = []
                            st.rerun()
                else:
                    st.info("Add teams from the left to build your top 25.")

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
