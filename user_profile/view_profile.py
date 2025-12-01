# viewprofile.py – Fancy version
import streamlit as st
from data_base.database import get_user_by_id
import hashlib

def _gravatar(email, size=120):
    """Generate Gravatar URL"""
    digest = hashlib.md5(email.lower().encode('utf-8')).hexdigest()
    return f"https://www.gravatar.com/avatar/{digest}?d=identicon&s={size}"

def show_view_profile_dialog():
    user = st.session_state.get("user")
    if not user:
        st.error("No user session found.")
        return

    user_id = user.get("id")
    fresh_user = get_user_by_id(user_id)
    if not fresh_user:
        st.error("Could not load user data.")
        return

    u = dict(fresh_user) if not isinstance(fresh_user, dict) else fresh_user

    @st.dialog(title="Your Profile", width="stretch")
    def profile_dialog():
        st.markdown(
            f"""
            <div style="text-align:center;">
                <img src="{_gravatar(u.get('email',''))}" width="120" style="border-radius:50%; border:4px solid #4d79ff;">
                <h2>{u.get('first_name','')}{' '+u.get('last_name','') if u.get('last_name') else ''}</h2>
                <p>@{u.get('username')}</p>
            </div>
            """,
            unsafe_allow_html=True,
        )

        st.divider()

        data = {
            "First Name": u.get("first_name") or "—",
            "Last Name": u.get("last_name") or "—",
            "Username": u.get("username") or "—",
            "Email": u.get("email") or "—",
            "Member Since": (u.get("created_at") or "").split(".")[0],
            "User ID": str(user_id),
        }

        for label, value in data.items():
            col1, col2 = st.columns([1, 3])
            with col1:
                st.markdown(f"**{label}**")
            with col2:
                if label == "Email":
                        st.code(value)
                else:
                        st.write(value)


    profile_dialog()