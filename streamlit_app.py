import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from streamlit_sortables import sort_items
from datetime import datetime, timedelta
import pytz
from collections import defaultdict
import hashlib
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

st.set_page_config(page_title="Associated Goys Top 25 Poll", layout="wide")

st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Bebas+Neue&display=swap');
    html, body, [class*="css"] { font-family: 'Bebas Neue', sans-serif !important; letter-spacing: 2px !important; }
    h1, h2, h3, h4, h5, h6, .stSubheader, .stMarkdown, button, .stButton > button, .stTextInput label, .stTextInput input {
        font-family: 'Bebas Neue', sans-serif !important; letter-spacing: 2px !important;
    }
    .block-container { padding-top: 1.5rem !important; padding-bottom: 0.5rem !important; }
    h1 { font-size: 2rem !important; margin-bottom: 0.6rem !important; margin-top: 0.5rem !important; text-align: center !important; }
    h2, h3 { font-size: 1.15rem !important; margin: 0.3rem 0 !important; text-align: center !important; }
    h1 a, h2 a, h3 a, h4 a, h5 a, h6 a, .stSubheader a, [data-testid="stHeader"] a { display: none !important; pointer-events: none !important; }
    button[data-baseweb="tab"] { font-size: 1.05rem !important; font-weight: 600 !important; padding: 0.4rem 1rem !important; }
    button[data-baseweb="tab"][aria-selected="true"], button[data-baseweb="tab"]:hover { background-color: #D4AF37 !important; color: #1a1a1a !important; }
    .stButton > button {
        background-color: #D4AF37 !important; color: #1a1a1a !important; border: none !important; text-align: left !important;
        padding: 7px 12px !important; margin: 2px 0 !important; border-radius: 5px !important; font-size: 0.95rem !important;
        font-weight: 700 !important; width: 100% !important; font-family: 'Bebas Neue', sans-serif !important; letter-spacing: 2px !important;
    }
    .stButton > button:hover { background-color: #E6C200 !important; }
    div[data-testid="stButton"] > button[kind="primary"] {
        background-color: #4CAF50 !important; color: #ffffff !important; border: 3px solid #00FF00 !important; box-shadow: 0 0 8px #00FF00 !important;
    }
    div[data-testid="stButton"] > button[kind="primary"]:hover { background-color: #66BB6A !important; border: 3px solid #00FF00 !important; }
    div[data-testid="stButton"] > button:disabled {
        background-color: #d32f2f !important; color: #ffffff !important; opacity: 1 !important; cursor: not-allowed !important; border: none !important; box-shadow: none !important;
    }
    .center-header { font-size: 1.45rem !important; margin: 0.2rem 0 0.2rem 0 !important; text-align: center !important; font-weight: 700 !important; }
    .side-header { font-size: 1.05rem !important; margin: 0.4rem 0 0.2rem 0 !important; text-align: center !important; font-weight: 700 !important; font-family: 'Bebas Neue', sans-serif !important; letter-spacing: 2px !important; }
    .rank-numbers { text-align: right; padding-right: 2px; color: #ffffff !important; font-weight: 700; font-size: 0.9rem; margin-top: 4px; }
    .rank-numbers div { height: 28px; display: flex; align-items: flex-end; justify-content: flex-end; padding-bottom: 4px; }
    [data-testid="column"] { padding-left: 0.15rem !important; padding-right: 0.15rem !important; }
    .results-table { width: 100%; border-collapse: collapse; font-size: 0.78rem; font-family: 'Bebas Neue', sans-serif; letter-spacing: 1px; table-layout: fixed; }
    .results-table th { text-align: center !important; padding: 6px 12px; border-bottom: 1px solid #444; font-weight: 700; font-size: 1.15rem !important; white-space: nowrap; }
    .results-table td { padding: 2px 6px; border-bottom: 1px solid #333; font-size: 0.78rem; }
    .results-table th.rank, .results-table td.rank { width: 160px; max-width: 160px; text-align: center !important; }
    .results-table th.team { text-align: center !important; }
    .results-table td.team { width: auto; text-align: left !important; }
    .results-table th.num, .results-table td.num { width: 160px; max-width: 160px; text-align: center !important; white-space: nowrap; }
    .results-table-container { height: 680px; overflow-y: auto; }
</style>
""", unsafe_allow_html=True)

CENTER_STYLE = """
.sortable-container { background: transparent !important; margin-top: -8px !important; }
.sortable-container-body { background: transparent !important; max-height: 700px !important; min-height: 700px !important; overflow-y: hidden !important; padding-top: 0 !important; margin-top: 0 !important; }
.sortable-item { background-color: #4CAF50 !important; color: #1a1a1a !important; text-align: left !important; padding: 4px 10px !important; margin: 0 !important; border-radius: 4px !important; font-size: 0.9rem !important; line-height: 1.2 !important; height: 28px !important; min-height: 28px !important; box-sizing: border-box !important; font-family: 'Bebas Neue', sans-serif !important; letter-spacing: 2px !important; font-weight: 700 !important; display: flex !important; align-items: center !important; }
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
        if 11 <= n % 100 <= 13: suffix = "th"
        else: suffix = {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
        return f"{n}{suffix}"
    def fmt(d): return f"{d.strftime('%B')} {ordinal(d.day)}"
    return f"{fmt(monday)} - {fmt(sunday)}"

def is_open():
    now = datetime.now(ET)
    weekday = now.weekday()
    if weekday == 6: return False
    if weekday == 5 and now.hour == 23 and now.minute >= 59: return False
    return True

SCOPES = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]

@st.cache_resource
def get_gsheet_client():
    creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=SCOPES)
    return gspread.authorize(creds)

def open_sheet(gc):
    try:
        return gc.open_by_url(st.secrets["gsheets"]["spreadsheet_url"])
    except Exception as e:
        st.error(f"Could not open Google Sheet: {type(e).__name__}")
        st.code(str(e))
        return None

def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()

@st.cache_data(ttl=120)
def get_users_records(_gc):
    sh = open_sheet(_gc)
    if not sh:
        return []
    try:
        return sh.worksheet("Users").get_all_records()
    except Exception:
        return []

def get_users_sheet(gc):
    sh = open_sheet(gc)
    if not sh:
        return None
    try:
        return sh.worksheet("Users")
    except Exception:
        ws = sh.add_worksheet(title="Users", rows=200, cols=5)
        ws.append_row(["Username", "PasswordHash", "Email", "CreatedAt", "DisplayName"])
        st.cache_data.clear()
        return ws

def user_exists(gc, username: str) -> bool:
    records = get_users_records(gc)
    return any(r.get("Username", "").lower() == username.lower() for r in records)

def create_user(gc, username: str, password: str, email: str) -> bool:
    if user_exists(gc, username):
        return False
    ws = get_users_sheet(gc)
    if not ws:
        return False
    ws.append_row([
        username.strip(),
        hash_password(password),
        email.strip().lower(),
        datetime.now(ET).strftime("%Y-%m-%d %H:%M:%S"),
        username.strip()
    ])
    st.cache_data.clear()
    return True

def verify_user(gc, username: str, password: str) -> bool:
    records = get_users_records(gc)
    for r in records:
        if r.get("Username", "").lower() == username.lower():
            return r.get("PasswordHash") == hash_password(password)
    return False

def get_user_record(gc, username: str):
    records = get_users_records(gc)
    for r in records:
        if r.get("Username", "").lower() == username.lower():
            return r
    return None

def update_password(gc, username: str, new_password: str) -> bool:
    ws = get_users_sheet(gc)
    if not ws:
        return False
    records = ws.get_all_records()
    for i, r in enumerate(records, start=2):
        if r.get("Username", "").lower() == username.lower():
            ws.update_cell(i, 2, hash_password(new_password))
            st.cache_data.clear()
            return True
    return False

def update_display_name(gc, username: str, new_display_name: str) -> bool:
    ws = get_users_sheet(gc)
    if not ws:
        return False
    records = ws.get_all_records()
    for i, r in enumerate(records, start=2):
        if r.get("Username", "").lower() == username.lower():
            ws.update_cell(i, 5, new_display_name.strip())
            st.cache_data.clear()
            return True
    return False

def log_vote(gc, username, week_number):
    sh = open_sheet(gc)
    if not sh:
        return
    try:
        ws = sh.worksheet("VoteLog")
    except Exception:
        ws = sh.add_worksheet(title="VoteLog", rows=1000, cols=3)
        ws.append_row(["Username", "Week", "Timestamp"])
    records = ws.get_all_records()
    if any(r.get("Username") == username and str(r.get("Week")) == str(week_number) for r in records):
        return
    ws.append_row([username, week_number, datetime.now(ET).strftime("%Y-%m-%d %H:%M:%S")])
    st.cache_data.clear()

@st.cache_data(ttl=180)
def get_votelog_records(_gc):
    sh = open_sheet(_gc)
    if not sh:
        return []
    try:
        return sh.worksheet("VoteLog").get_all_records()
    except Exception:
        return []

def get_consecutive_weeks(gc, username):
    records = get_votelog_records(gc)
    weeks = sorted({int(r["Week"]) for r in records if r.get("Username") == username and str(r.get("Week", "")).isdigit()})
    if not weeks:
        return 0
    current = get_current_week_number()
    streak = 1
    for i in range(len(weeks) - 1, 0, -1):
        if weeks[i] == weeks[i-1] + 1:
            streak += 1
        else:
            break
    last_voted = weeks[-1]
    if last_voted < current - 1:
        return 0
    return streak

def get_calculated_weight(consecutive):
    if consecutive <= 0:
        return 1.0
    bonus = consecutive // 4
    return float(min(5, 1 + bonus))

def get_effective_weight(gc, username):
    consecutive = get_consecutive_weeks(gc, username)
    return get_calculated_weight(consecutive)

def send_email(to_email: str, subject: str, body: str) -> bool:
    try:
        msg = MIMEMultipart()
        msg["From"] = st.secrets["email"]["sender_email"]
        msg["To"] = to_email
        msg["Subject"] = subject
        msg.attach(MIMEText(body, "plain"))
        server = smtplib.SMTP(st.secrets["email"]["smtp_server"], int(st.secrets["email"]["smtp_port"]))
        server.starttls()
        server.login(st.secrets["email"]["sender_email"], st.secrets["email"]["sender_password"])
        server.send_message(msg)
        server.quit()
        return True
    except Exception as e:
        print(f"Email error: {e}")
        return False

def send_saturday_reminders(gc):
    now = datetime.now(ET)
    if now.weekday() != 5:
        return
    week = get_current_week_number()
    sh = open_sheet(gc)
    if not sh:
        return
    try:
        meta = sh.worksheet("AppMeta")
        last = int(meta.acell("B2").value or 0)
    except Exception:
        meta = sh.add_worksheet(title="AppMeta", rows=5, cols=2)
        meta.append_row(["Key", "Value"])
        meta.append_row(["LastReminderWeek", "0"])
        last = 0
    if last >= week:
        return

    records = get_users_records(gc)
    sent = 0
    for u in records:
        email = u.get("Email", "").strip()
        if email:
            subject = f"Last day to vote — Week {week} of the AG Top 25"
            body = (f"Hi {u.get('DisplayName', u.get('Username'))},\n\n"
                    f"Today (Saturday) is the last day to submit or update your rankings for Week {week}.\n\n"
                    f"Voting closes at 11:59 PM ET tonight.\n\n"
                    f"https://your-app-url.streamlit.app\n\n— AG Top 25")
            if send_email(email, subject, body):
                sent += 1
    meta.update_acell("B2", str(week))

def should_archive_previous_week(gc, current_week):
    if current_week <= 1:
        return None
    prev = current_week - 1
    sh = open_sheet(gc)
    if not sh:
        return None
    titles = [ws.title for ws in sh.worksheets()]
    if f"Week {prev} Results" not in titles:
        return prev
    return None

def archive_and_reset(gc, week_to_archive):
    sh = open_sheet(gc)
    if not sh:
        return False
    try:
        results = load_results(gc)
        tab_name = f"Week {week_to_archive} Results"
        titles = [ws.title for ws in sh.worksheets()]
        if tab_name not in titles:
            new_ws = sh.add_worksheet(title=tab_name, rows=60, cols=5)
            rows = [["Rank", "Team", "Points", "First Place Votes"]]
            if not results.empty:
                for i, row in results.head(50).iterrows():
                    rows.append([i + 1, row["Team"], int(row["Points"]), int(row["First Place Votes"])])
            else:
                rows.append(["", "(No submissions)", "", ""])
            new_ws.update("A1", rows)
        ws = sh.worksheet("Submissions")
        if ws.row_count > 1:
            ws.batch_clear(["A2:AA1000"])
        st.cache_data.clear()
        return True
    except Exception as e:
        st.error(f"Archive failed: {e}")
        return False

def save_submission(gc, username, ranking):
    sh = open_sheet(gc)
    if not sh:
        return False
    try:
        ws = sh.worksheet("Submissions")
        records = ws.get_all_records()
        row_num = next((i for i, rec in enumerate(records, start=2) if rec.get("Person") == username), None)
        timestamp = datetime.now(ET).strftime("%Y-%m-%d %H:%M:%S")
        row_data = [timestamp, username] + ranking + [""] * (25 - len(ranking))
        if row_num:
            ws.update(f"A{row_num}:AA{row_num}", [row_data])
        else:
            ws.append_row(row_data)
        st.cache_data.clear()
        log_vote(gc, username, get_current_week_number())
        return True
    except Exception as e:
        st.error(f"Save failed: {e}")
        return False

def load_previous_aggregate(gc, week_number):
    if week_number <= 1:
        return []
    sh = open_sheet(gc)
    if not sh:
        return []
    try:
        ws = sh.worksheet(f"Week {week_number - 1} Results")
        values = ws.get_all_values()
        teams = [row[1].strip() for row in values[1:] if len(row) > 1 and row[1].strip() and not row[1].startswith("(")]
        return teams[:25]
    except Exception:
        return []

def load_user_previous_ranking(gc, username):
    sh = open_sheet(gc)
    if not sh:
        return []
    try:
        ws = sh.worksheet("Submissions")
        records = [r for r in ws.get_all_records() if r.get("Person") == username]
        if not records:
            return []
        records.sort(key=lambda r: r.get("Timestamp", ""), reverse=True)
        latest = records[0]
        return [latest.get(f"Rank{i}") for i in range(1, 26) if latest.get(f"Rank{i}")]
    except Exception:
        return []

@st.cache_data(ttl=90)
def load_results(_gc):
    sh = open_sheet(_gc)
    if not sh:
        return pd.DataFrame()
    try:
        submissions = sh.worksheet("Submissions").get_all_records()
        if not submissions:
            return pd.DataFrame()

        try:
            weights_df = pd.DataFrame(sh.worksheet("Weights").get_all_records())
        except Exception:
            weights_df = pd.DataFrame()

        votelog = get_votelog_records(_gc)

        df = pd.DataFrame(submissions)
        df["Timestamp"] = pd.to_datetime(df["Timestamp"])
        latest = df.sort_values("Timestamp").groupby("Person").tail(1)

        points = defaultdict(float)
        firsts = defaultdict(float)

        current_week = get_current_week_number()

        for _, row in latest.iterrows():
            person = row["Person"]
            w = 1.0

            # Prefer explicit weight from Weights sheet
            if not weights_df.empty and "Person" in weights_df.columns and person in weights_df["Person"].values:
                w = float(weights_df.loc[weights_df["Person"] == person, "Weight"].iloc[0])
            else:
                # Calculate from VoteLog in memory
                weeks = sorted({
                    int(r["Week"]) for r in votelog
                    if r.get("Username") == person and str(r.get("Week", "")).isdigit()
                })
                if weeks:
                    streak = 1
                    for i in range(len(weeks) - 1, 0, -1):
                        if weeks[i] == weeks[i - 1] + 1:
                            streak += 1
                        else:
                            break
                    last_voted = weeks[-1]
                    if last_voted >= current_week - 1:
                        bonus = streak // 4
                        w = float(min(5, 1 + bonus))

            for pos in range(1, 26):
                team = row.get(f"Rank{pos}")
                if team:
                    points[team] += (26 - pos) * w
                    if pos == 1:
                        firsts[team] += w

        results = [
            {"Team": t, "Points": int(round(p)), "First Place Votes": int(round(firsts[t]))}
            for t, p in points.items()
        ]
        results.sort(key=lambda x: (-x["Points"], -x["First Place Votes"]))
        return pd.DataFrame(results)

    except Exception as e:
        st.error(f"Could not load results: {e}")
        return pd.DataFrame()

@st.cache_data(ttl=600)
def load_teams(_gc):
    sh = open_sheet(_gc)
    if not sh:
        return []
    try:
        values = sh.worksheet("Teams").col_values(1)
        teams = [v.strip() for v in values if v and v.strip() and v.strip().lower() != "team"]
        return teams
    except Exception as e:
        st.error(f"Could not load teams from sheet: {e}")
        return []

def get_display_name(username):
    display_names = st.secrets.get("display_names", {})
    if username in display_names:
        return display_names[username]
    gc = get_gsheet_client()
    rec = get_user_record(gc, username)
    return rec.get("DisplayName", username) if rec else username

def check_login():
    if "authenticated" not in st.session_state:
        st.session_state.authenticated = False
        st.session_state.username = ""
    if not st.session_state.authenticated:
        st.title("Associated Goys Top 25 Poll")
        tab_login, tab_signup = st.tabs(["Log In", "Create Account"])
        with tab_login:
            username = st.text_input("Username", key="login_user")
            password = st.text_input("Password", type="password", key="login_pass")
            if st.button("Log In", key="login_btn"):
                gc = get_gsheet_client()
                if verify_user(gc, username, password):
                    st.session_state.authenticated = True
                    st.session_state.username = username
                    st.rerun()
                else:
                    st.error("Invalid username or password.")
        with tab_signup:
            new_user = st.text_input("Choose a username", key="su_user")
            new_email = st.text_input("Email", key="su_email")
            new_pass = st.text_input("Password", type="password", key="su_pass")
            new_pass2 = st.text_input("Confirm password", type="password", key="su_pass2")
            if st.button("Create Account", key="signup_btn"):
                if not new_user or not new_email or not new_pass:
                    st.error("All fields are required.")
                elif new_pass != new_pass2:
                    st.error("Passwords do not match.")
                elif len(new_pass) < 6:
                    st.error("Password must be at least 6 characters.")
                else:
                    gc = get_gsheet_client()
                    if user_exists(gc, new_user):
                        st.error("Username taken.")
                    elif create_user(gc, new_user, new_pass, new_email):
                        st.success("Account created! You can now log in.")
                    else:
                        st.error("Could not create account.")
        return False
    return True

def render_results_table(df, start_rank=1):
    html = '<div class="results-table-container"><table class="results-table"><thead><tr>'
    html += '<th class="rank">Rank</th><th class="team">Team</th><th class="num">Points</th><th class="num">First Place Votes</th></tr></thead><tbody>'
    for idx, row in df.iterrows():
        rank = start_rank + idx
        html += f'<tr><td class="rank">{rank}</td><td class="team">{row["Team"]}</td><td class="num">{int(row["Points"])}</td><td class="num">{row["First Place Votes"]}</td></tr>'
    html += '</tbody></table></div>'
    st.markdown(html, unsafe_allow_html=True)

# ---------------------------------------------------------------------------
if not check_login():
    st.stop()

display_name = get_display_name(st.session_state.username)
week_number = get_current_week_number()
date_range = format_date_range()

st.markdown(f"<div style='text-align: left; margin-top: 1.1rem; font-size: 0.95rem; color: #aaaaaa; position: absolute;'>Logged in as: {display_name}</div>", unsafe_allow_html=True)
st.title(f"Associated Goys Top 25 Poll | Week {week_number} | {date_range}")

gc = get_gsheet_client()

# Run maintenance less aggressively
if "last_maintenance" not in st.session_state:
    st.session_state.last_maintenance = datetime.min.replace(tzinfo=ET)

if (datetime.now(ET) - st.session_state.last_maintenance).total_seconds() > 300:
    send_saturday_reminders(gc)
    week_to_archive = should_archive_previous_week(gc, week_number)
    if week_to_archive:
        with st.spinner(f"Finalizing Week {week_to_archive}..."):
            if archive_and_reset(gc, week_to_archive):
                st.success(f"Week {week_to_archive} finalized. New week is ready.")
                st.rerun()
    st.session_state.last_maintenance = datetime.now(ET)

teams = load_teams(gc)
tab1, tab2, tab3 = st.tabs(["Submit Rankings", "Current Results", "Account"])

with tab1:
    if not is_open():
        st.error("Submissions are closed. Voting reopens Monday at midnight ET (cutoff Saturday 11:59 PM ET).")
    else:
        st.info(f"Voting as: **{display_name}**")

        if "ranking" not in st.session_state or not st.session_state.get("ranking"):
            own = load_user_previous_ranking(gc, st.session_state.username)
            if own:
                st.session_state.ranking = own
            else:
                st.session_state.ranking = load_previous_aggregate(gc, week_number) or []

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
                numbers_html = '<div class="rank-numbers">' + ''.join(f'<div>{i}.</div>' for i in range(1, 26)) + '</div>'
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
            st.markdown('<div class="side-header">CONTROLS</div>', unsafe_allow_html=True)
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
            st.write("")
            has_25 = len(st.session_state.ranking) == 25
            if has_25:
                if st.button("SUBMIT/UPDATE RANKINGS", type="primary", use_container_width=True, key="submit_btn"):
                    if save_submission(gc, st.session_state.username, st.session_state.ranking):
                        st.session_state.just_submitted = True
                        st.rerun()
            else:
                st.button("SUBMIT/UPDATE RANKINGS", disabled=True, use_container_width=True, key="submit_btn_disabled")
            if st.session_state.get("just_submitted"):
                st.success(f"Rankings Submitted — you may update until the end of the Week {week_number} window.")
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
            render_results_table(top25.reset_index(drop=True), start_rank=1)
        with col_res_right:
            st.markdown("**Others Receiving Votes**")
            if not others.empty:
                render_results_table(others.reset_index(drop=True), start_rank=26)
            else:
                st.info("No other teams received votes.")
    else:
        st.info("No submissions yet (or sheet temporarily unavailable).")

with tab3:
    st.markdown("### Account Settings")
    user = get_user_record(gc, st.session_state.username)
    if not user:
        st.error("Could not load account info.")
    else:
        st.write(f"**Username:** {user.get('Username')}")
        st.write(f"**Email:** {user.get('Email') or '_(not set)_'}")
        st.write(f"**Member since:** {user.get('CreatedAt', '—')}")

        consecutive = get_consecutive_weeks(gc, st.session_state.username)
        weight = get_effective_weight(gc, st.session_state.username)
        st.write(f"**Consecutive weeks voted:** {consecutive}")
        st.write(f"**Current weight:** {weight:.0f}×")

        st.divider()
        st.subheader("Change Display Name")
        new_display = st.text_input("New display name", value=user.get("DisplayName", ""), key="new_display")
        if st.button("Update Display Name", key="update_display"):
            if not new_display or not new_display.strip():
                st.error("Display name cannot be empty.")
            elif update_display_name(gc, st.session_state.username, new_display):
                st.success("Display name updated.")
                st.rerun()
            else:
                st.error("Failed to update display name.")

        st.divider()
        st.subheader("Change Password")

        current = st.text_input("Current password", type="password", key="acct_current")
        new1 = st.text_input("New password", type="password", key="acct_new1")
        new2 = st.text_input("Confirm new password", type="password", key="acct_new2")

        if st.button("Update Password", key="acct_update"):
            if not current or not new1:
                st.error("All fields required.")
            elif new1 != new2:
                st.error("New passwords do not match.")
            elif len(new1) < 6:
                st.error("Password must be at least 6 characters.")
            elif hash_password(current) != user.get("PasswordHash"):
                st.error("Current password is incorrect.")
            else:
                if update_password(gc, st.session_state.username, new1):
                    st.success("Password updated successfully.")
                    st.rerun()
                else:
                    st.error("Failed to update password.")
