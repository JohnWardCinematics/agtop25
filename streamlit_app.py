import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from streamlit_sortables import sort_items
from datetime import datetime
import pytz
from collections import defaultdict
import time

st.set_page_config(page_title="Top 25 Rankings", layout="wide")

ET = pytz.timezone("America/New_York")
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
    if now.weekday() == 6 and (now.hour > 23 or (now.hour == 23 and now.minute >= 59)):
        return False
    return True

@st.cache_data
def load_teams():
    try:
        df = pd.read_csv("teams.csv")
        return df["Team"].dropna().astype(str).str.strip().tolist()
    except Exception as e:
        st.error(f"Could not load teams.csv: {e}")
        return []

def open_sheet(gc, retries=3):
    url = st.secrets["gsheets"]["spreadsheet_url"]
    for i in range(retries):
        try:
            return gc.open_by_url(url)
        except Exception as e:
            if i == retries - 1:
                st.error(f"Could not open Google Sheet: {type(e).__name__}")
                st.code(str(e))
                return None
            time.sleep(1.5)
    return None

def get_latest_submissions(gc):
    sh = open_sheet(gc)
    if not sh:
        return pd.DataFrame()
    try:
        ws = sh.worksheet("Submissions")
        data = ws.get_all_records()
        if not data:
            return pd.DataFrame()
        df = pd.DataFrame(data)
        df["Timestamp"] = pd.to_datetime(df["Timestamp"])
        return df.sort_values("Timestamp").groupby("Person").tail(1)
    except Exception as e:
        st.error(f"Error reading submissions: {e}")
        return pd.DataFrame()

def save_submission(gc, person, ranking):
    sh = open_sheet(gc)
    if not sh:
        st.error("Could not save — sheet unavailable.")
        return
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

def aggregate(gc):
    latest = get_latest_submissions(gc)
    if latest.empty:
        return pd.DataFrame()
    sh = open_sheet(gc)
    if not sh:
        return pd.DataFrame()
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

# --- UI ---
st.title("Top 25 Rankings")
gc = get_gsheet_client()

tab1, tab2 = st.tabs(["Submit Ranking", "Current Results"])

with tab1:
    if not is_open():
        st.error("Submissions are closed until next week (cutoff is Sunday 11:59 PM ET).")
    else:
        person = st.text_input("Your name (used to identify & overwrite your ballot)")
        if person:
            teams = load_teams()
            if "ranking" not in st.session_state:
                st.session_state.ranking = []

            col1, col2 = st.columns(2)

            with col1:
                st.subheader("Available Teams")
                for team in teams:
                    if team not in st.session_state.ranking:
                        c1, c2 = st.columns([3, 1])
                        c1.write(team)
                        if c2.button("Add", key=f"add_{team}"):
                            if len(st.session_state.ranking) < 25:
                                st.session_state.ranking.append(team)
                                st.rerun()

            with col2:
                st.subheader("Your Ranking (drag to reorder)")
                if st.session_state.ranking:
                    ranked = sort_items(st.session_state.ranking, key="rank_sort")
                    st.session_state.ranking = ranked
                    for i, team in enumerate(st.session_state.ranking, 1):
                        st.write(f"**{i}.** {team}")
                    if st.button("Submit / Update Ranking", type="primary"):
                        save_submission(gc, person.strip(), st.session_state.ranking)
                        st.success("Ranking saved.")
                        st.session_state.ranking = []
                else:
                    st.info("Add teams from the left.")

with tab2:
    st.subheader("Weighted Aggregate Top 25")
    results = aggregate(gc)
    if not results.empty:
        st.dataframe(results.head(25), use_container_width=True)
    else:
        st.info("No submissions yet.")
