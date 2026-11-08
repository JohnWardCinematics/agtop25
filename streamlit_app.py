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
    h1 a, h2 a, h3 a, h4 a, h5 a, h6 a,
    .stSubheader a, [data-testid="stHeader"] a {
        display: none !important;
        pointer-events: none !important;
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
        margin: 0.2rem 0 0.2rem 0 !important;
        text-align: center !important;
        font-weight: 700 !important;
    }

    .side-header {
        font-size: 1.05rem !important;
        margin: 0.4rem 0 0.2rem 0 !important;
        text-align: center !important;
        font-weight: 700 !important;
        font-family: 'Bebas Neue', sans-serif !important;
        letter-spacing: 2px !important;
    }

    .rank-numbers {
        text-align: right;
        padding-right: 2px;
        color: #ffffff !important;
        font-weight: 700;
        font-size: 0.9rem;
        margin-top: 4px;
    }
    .rank-numbers div {
        height: 28px;
        display: flex;
        align-items: flex-end;
        justify-content: flex-end;
        padding-bottom: 4px;
    }

    [data-testid="column"] {
        padding-left: 0.15rem !important;
        padding-right: 0.15rem !important;
    }

    div[data-testid="stDataFrame"] {
        font-size: 0.78rem !important;
    }
    div[data-testid="stDataFrame"] td, 
    div[data-testid="stDataFrame"] th {
        padding: 1px 4px !important;
        line-height: 1.15 !important;
    }
</style>
""", unsafe_allow_html=True)

CENTER_STYLE = """
.sortable-container {
    background: transparent !important;
    margin-top: -8px !important;
}
.sortable-container-body {
    background: transparent !important;
    max-height: 700px !important;
    min-height: 700px !important;
    overflow-y: hidden !important;
    padding-top: 0 !important;
    margin-top: 0 !important;
}
.sortable-item {
    background-color: #4CAF50 !important;
    color: #1a1a1a !important;
    text-align: left !important;
    padding: 4px 10px !important;
    margin: 0 !important;
    border-radius: 4px !important;
    font-size: 0.9rem !important;
    line-height: 1.2 !important;
    height: 28px !important;
    min-height: 28px !important;
    box-sizing: border-box !important;
    font-family: 'Bebas Neue', sans-serif !important;
    letter-spacing: 2px !important;
    font-weight: 700 !important;
    display: flex !important;
    align-items: center !important;
}
.sortable-item:hover { background-color: #66BB6A !important; }
"""

ET = pytz.timezone("America/New_York")

WEEK_1_START = datetime(2026, 9, 28, tzinfo=ET)

def get_current_week_number():
    now = datetime.now(ET)
    days_since_start = (now - WEEK_1_START).days
    return max(1, (days_since_start // 7) + 1)

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
        return f"{d.strftime('%B')} {ordinal(d.day)}"
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

def archive_week(gc, week_number):
    sh = open_sheet(gc)
    if not sh:
        return False
    tab_name = f"Week {week_number}"
    try:
        existing = [ws.title for ws in sh.worksheets()]
        if tab_name in existing:
            return True
        source = sh.worksheet("Submissions")
        data = source.get_all_values()
        new_ws = sh.add_worksheet(title=tab_name, rows=len(data)+10, cols=30)
        if data:
            new_ws.update("A1", data)
        return True
    except Exception as e:
        st.error(f"Archive failed: {e}")
        return False

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
            ws.update(f"A{row_num}:AA{row_num}", [row_data])
        else:
            ws.append_row(row_data)
        st.cache_data.clear()
        return True
    except Exception as e:
        st.error(f"Save failed: {e}")
        return False

def load_previous_ranking(gc, person):
    sh = open_sheet(gc)
    if not sh:
        return []
    try:
        ws = sh.worksheet("Submissions")
        records = ws.get_all_records()
        user_rows = [r for r in records if r.get("Person") == person]
        if not user_rows:
            return []
        user_rows.sort(key=lambda r: r.get("Timestamp", ""), reverse=True)
        latest = user_rows[0]
        ranking = []
        for i in range(1, 26):
            team = latest.get(f"Rank{i}")
            if team:
                ranking.append(team)
        return ranking
    except Exception:
        return []

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

def get_display_name(username):
    display_names = st.secrets.get("display_names", {})
    return display_names.get(username, username)

def check_login():
    if "authenticated" not in st.session_state:
        st.session_state.authenticated = False
        st.session_state.username = ""

    if not st.session_state.authenticated:
        st.title("Associated Goys Top 25 Poll")
        st.write("Please log in with your voter credentials.")
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        if st.button("Log In"):
            voters = st.secrets.get("voters", {})
            if username in voters and voters[username] == password:
                st.session_state.authenticated = True
                st.session_state.username = username
                st.rerun()
            else:
                st.error("Invalid username or password.")
        return False
    return True

if not check_login():
    st.stop()

display_name = get_display_name(st.session_state.username)
week_number = get_current_week_number()
date_range = format_date_range()

# Main header with logged-in status on the left
header_left, header_center = st.columns([1, 4])
with header_left:
    st.markdown(f"<div style='text-align: left; margin-top: 1.1rem; font-size: 0.95rem; color: #aaaaaa;'>Logged in as: {display_name}</div>", unsafe_allow_html=True)
with header_center:
    st.title(f"Associated Goys Top 25 Poll | Week {week_number} | {date_range}")

gc = get_gsheet_client()

if not is_open() and week_number > 1:
    archive_week(gc, week_number - 1)

teams = load_teams()

tab1, tab2 = st.tabs(["Submit Rankings", "Current Results"])

with tab1:
    if not is_open():
        st.error("Submissions are closed until next week (cutoff is Sunday 11:59 PM ET).")
    else:
        st.info(f"Voting as: **{display_name}**")

        if "ranking" not in st.session_state:
            previous = load_previous_ranking(gc, display_name)
            st.session_state.ranking = previous if previous else []

        if "show_remove" not in st.session_state:
            st.session_state.show_remove = False

        if "confirm_clear" not in st.session_state:
            st.session_state.confirm_clear = False

        col_left, col_center, col_right = st.columns([1, 2, 1])

        with col_left:
            st.markdown('<div class="side-header">Available Teams (click to add)</div>', unsafe_allow_html=True)
            available = [t for t in teams if t not in st.session_state.ranking]
            with st.container(height=700):
                for team in available:
                    if st.button(team, key=f"add_{team}", use_container_width=True):
                        if len(st.session_state.ranking) < 25:
                            st.session_state.ranking.append(team)
                            st.rerun()

        with col_center:
            st.markdown(f'<h3 class="center-header">{display_name} Rankings (drag to reorder)</h3>', unsafe_allow_html=True)

            num_col, sort_col = st.columns([0.06, 0.94])

            with num_col:
                numbers_html = '<div class="rank-numbers">'
                for i in range(1, 26):
                    numbers_html += f'<div>{i}.</div>'
                numbers_html += '</div>'
                st.markdown(numbers_html, unsafe_allow_html=True)

            with sort_col:
                center_result = sort_items(
                    st.session_state.ranking,
                    direction="vertical",
                    key=f"ranking_{len(st.session_state.ranking)}",
                    custom_style=CENTER_STYLE
                )
                if center_result != st.session_state.ranking:
                    st.session_state.ranking = center_result
                    st.rerun()

        with col_right:
            st.markdown('<div class="side-header">Submit</div>', unsafe_allow_html=True)
            
            # CLEAR ALL with confirmation
            if not st.session_state.confirm_clear:
                if st.button("CLEAR ALL", use_container_width=True, key="clear_all"):
                    st.session_state.confirm_clear = True
                    st.rerun()
            else:
                st.warning("Clear all rankings?")
                c1, c2 = st.columns(2)
                with c1:
                    if st.button("Yes", key="yes_clear", use_container_width=True):
                        st.session_state.ranking = []
                        st.session_state.confirm_clear = False
                        st.session_state.show_remove = False
                        st.rerun()
                with c2:
                    if st.button("No", key="no_clear", use_container_width=True):
                        st.session_state.confirm_clear = False
                        st.rerun()

            # REMOVE
            if st.button("REMOVE", use_container_width=True, key="toggle_remove"):
                st.session_state.show_remove = not st.session_state.show_remove
                st.rerun()
            
            if st.session_state.show_remove and st.session_state.ranking:
                to_remove = st.selectbox(
                    "Select team to remove",
                    options=[""] + st.session_state.ranking,
                    index=0,
                    key="remove_select",
                    label_visibility="collapsed"
                )
                if to_remove and st.button("Confirm Remove", key="confirm_remove", use_container_width=True):
                    st.session_state.ranking.remove(to_remove)
                    st.session_state.show_remove = False
                    st.rerun()

            st.write("")  # spacer
            if st.session_state.ranking:
                if st.button("SUBMIT/UPDATE RANKINGS", type="primary", use_container_width=True, key="submit_btn"):
                    if save_submission(gc, display_name, st.session_state.ranking):
                        st.session_state.ranking = []
                        st.session_state.just_submitted = True
                        st.rerun()
            else:
                st.button("SUBMIT/UPDATE RANKINGS", disabled=True, use_container_width=True, key="submit_btn_disabled")
            
            if st.session_state.get("just_submitted"):
                st.success(f"Rankings Submitted - You may continue to submit rankings until the end of the Week {week_number} window and they will overwrite previous submissions.")
                st.session_state.just_submitted = False

with tab2:
    header_col, refresh_col = st.columns([3, 1])
    with header_col:
        st.markdown("**Weighted Aggregate Results**")
    with refresh_col:
        if st.button("Refresh Results", use_container_width=True):
            st.cache_data.clear()
    
    results = load_results(gc)
    if not results.empty:
        top25 = results.head(25).copy()
        others = results.iloc[25:].copy()
        
        col_res_left, col_res_right = st.columns([1.2, 1])
        
        with col_res_left:
            st.markdown("**Top 25**")
            top25.insert(0, "Rank", range(1, len(top25) + 1))
            st.dataframe(
                top25[["Rank", "Team", "Points", "First Place Votes"]],
                use_container_width=True,
                height=680,
                hide_index=True
            )
        
        with col_res_right:
            st.markdown("**Others Receiving Votes**")
            if not others.empty:
                others.insert(0, "Rank", range(26, 26 + len(others)))
                st.dataframe(
                    others[["Rank", "Team", "Points", "First Place Votes"]],
                    use_container_width=True,
                    height=680,
                    hide_index=True
                )
            else:
                st.info("No other teams received votes.")
    else:
        st.info("No submissions yet (or sheet temporarily unavailable).")
