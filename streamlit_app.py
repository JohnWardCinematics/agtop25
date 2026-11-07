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
    .block-container { padding-top: 1rem !important; padding-bottom: 0.5rem !important; }
    h1 { font-size: 1.8rem !important; margin-bottom: 0.4rem !important; }
    h2, h3 { font-size: 1.15rem !important; margin: 0.3rem 0 !important; }
    button[data-baseweb="tab"] { font-size: 1.05rem !important; font-weight: 600 !important; padding: 0.4rem 1rem !important; }
    button[data-baseweb="tab"][aria-selected="true"],
    button[data-baseweb="tab"]:hover { background-color: #D4AF37 !important; color: #1a1a1a !important; }
    .stButton > button, button[kind="primary"] {
        background-color: #D4AF37 !important; color: #1a1a1a !important; border: none !important;
    }
    .stButton > button:hover, button[kind="primary"]:hover { background-color: #E6C200 !important; }
</style>
""", unsafe_allow_html=True)

MULTI_STYLE = """
.sortable-component {
    display: flex !important;
    width: 75vw !important;
    max-width: 75% !important;
    gap: 16px;
}
.sortable-container {
    background: transparent !important;
    border-radius: 6px;
    padding: 6px;
}
.sortable-container:first-child {
    flex: 0 0 33.33% !important;
    max-width: 33.33% !important;
}
.sortable-container:nth-child(2) {
    flex: 0 0 66.67% !important;
    max-width: 66.67% !important;
}
.sortable-container-header {
    font-weight: 600;
    margin-bottom: 6px;
}
.sortable-item {
    background-color: #D4AF37 !important;
    color: #1a1a1a !important;
    text-align: left !important;
    padding: 7px 12px !important;
    margin: 3px 0 !important;
    border-radius: 5px !important;
    font-size: 0.92rem !important;
    cursor: grab;
}
.sortable-item:hover { background-color: #E6C200 !important; }

.sortable-container:first-child .sortable-container-body {
    max-height: 720px !important;
    overflow-y: auto !important;
}
.sortable-container:nth-child(2) .sortable-container-body {
    min-height: 720px !important;
    max-height: 720px !important;
    overflow-y: hidden !important;
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
    now =
