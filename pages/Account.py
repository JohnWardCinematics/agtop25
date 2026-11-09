import streamlit as st
from streamlit_app import get_gsheet_client, get_user_record, update_password, hash_password

st.set_page_config(page_title="Account", layout="centered")

if not st.session_state.get("authenticated"):
    st.warning("Please log in from the main page first.")
    st.stop()

username = st.session_state.username
gc = get_gsheet_client()
user = get_user_record(gc, username)

st.title("Account Settings")

if not user:
    st.error("Could not load account info.")
    st.stop()

st.write(f"**Username:** {user.get('Username')}")
st.write(f"**Email:** {user.get('Email') or '_(not set)_'}")
st.write(f"**Member since:** {user.get('CreatedAt', '—')}")

st.divider()
st.subheader("Change Password")

current = st.text_input("Current password", type="password")
new1 = st.text_input("New password", type="password")
new2 = st.text_input("Confirm new password", type="password")

if st.button("Update Password"):
    if not current or not new1:
        st.error("All fields required.")
    elif new1 != new2:
        st.error("New passwords do not match.")
    elif len(new1) < 6:
        st.error("Password must be at least 6 characters.")
    elif hash_password(current) != user.get("PasswordHash"):
        st.error("Current password is incorrect.")
    else:
        if update_password(gc, username, new1):
            st.success("Password updated successfully.")
        else:
            st.error("Failed to update password.")
