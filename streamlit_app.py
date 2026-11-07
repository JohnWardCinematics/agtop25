import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from streamlit_sortables import sort_items
from datetime import datetime
import pytz
from collections import defaultdict

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
st.title("Top 25 Rankings")
gc = get_gsheet_client()
teams = load_teams()

tab1, tab2 = st.tabs(["Submit Ranking", "Current Results"])

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
                st.subheader("Your Ranking")
                if st.session_state.ranking:
                    # Numbered list for display + drag-and-drop
                    numbered = [f"{i+1}. {team}" for i, team in enumerate(st.session_state.ranking)]

                    reordered_numbered = sort_items(
                        numbered,
                        direction="vertical",
                        key="ranking_sortable"
                    )

                    # Strip the rank numbers back off
                    new_ranking = [item.split(". ", 1)[1] if ". " in item else item
                                   for item in reordered_numbered]

                    if new_ranking != st.session_state.ranking:
                        st.session_state.ranking = new_ranking
                        st.rerun()

                    st.caption("Drag teams up or down to reorder. Numbers update automatically.")

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
