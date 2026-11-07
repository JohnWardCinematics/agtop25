import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from streamlit_sortables import sort_items
from datetime import datetime
import pytz
from collections import defaultdict

st.set_page_config(page_title="Top 25 Rankings", layout="wide")

# --- Config ---
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

def load_teams(gc):
    sh = gc.open_by_url(st.secrets["gsheets"]["spreadsheet_url"])
    ws = sh.worksheet("Teams")
    return [r[0] for r in ws.get_all_values()[1:] if r and r[0].strip()]

def get_latest_submissions(gc):
    sh = gc.open_by_url(st.secrets["gsheets"]["spreadsheet_url"])
    ws = sh.worksheet("Submissions")
    data = ws.get_all_records()
    if not data:
        return pd.DataFrame()
    df = pd.DataFrame(data)
    df["Timestamp"] = pd.to_datetime(df["Timestamp"])
    return df.sort_values("Timestamp").groupby("Person").tail(1)

def save_submission(gc, person, ranking):
    sh = gc.open_by_url(st.secrets["gsheets"]["spreadsheet_url"])
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
    sh = gc.open_by_url(st.secrets["gsheets"]["spreadsheet_url"])
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
            teams = load_teams(gc)

            # Two-column drag-and-drop
            containers = [
                {"header": "Available Teams", "items": teams},
                {"header": "Your Ranking (drag here — top = #1)", "items": []}
            ]

            result = sort_items(containers, multi_containers=True, key="ranking_dnd")
            ranked = result[1]["items"][:25]

            # Live numbered preview
            st.subheader("Live Ranking Preview")
            if ranked:
                cols = st.columns([1, 4])
                for i, team in enumerate(ranked, 1):
                    cols[0].markdown(f"**{i}.**")
                    cols[1].write(team)
                if len(ranked) < 25:
                    st.caption(f"{25 - len(ranked)} slots remaining")
            else:
                st.info("Drag teams from the left column into the right column. Reorder them as needed.")

            if ranked and st.button("Submit / Update Ranking", type="primary"):
                save_submission(gc, person.strip(), ranked)
                st.success("Ranking saved (previous submission overwritten if it existed).")

with tab2:
    st.subheader("Weighted Aggregate Top 25")
    results = aggregate(gc)
    if not results.empty:
        st.dataframe(results.head(25), use_container_width=True)
        st.caption("Weights are applied from the Weights tab. Edit weights there anytime.")
    else:
        st.info("No submissions yet.")
