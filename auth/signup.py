# signup.py
import streamlit as st
import streamlit_antd_components as sac
import re
from data_base.database import create_user, get_user_by_username

# Define the dialog function at the top level (important!)
@st.dialog(title="Create your account", width="stretch")
def signup_dialog():
    st.markdown("""
    <style>
        .oauth-btn {display:flex;align-items:center;justify-content:center;gap:8px;
                    border:1px solid #e2e8f0;background:#fff;color:#333;padding:0.5rem;}
        .oauth-btn:hover {background:#f7fafc;}
        .divider {text-align:center;margin:1.5rem 0;color:#94a3c8;font-size:0.9rem;}
        .input-label {font-size:0.95rem;font-weight:500;color:#94a3c8;margin-bottom:0.25rem;}
        .optional {font-size:0.95rem;color:#94a3c8;font-weight:500;}
        .footer-text {text-align:center;color:#94a3c8;font-size:0.8rem;margin-top:1rem;}
    </style>
    """, unsafe_allow_html=True)

    st.markdown("**Welcome! Please fill in the details to get started.**")

    col_fn, col_ln = st.columns(2)
    with col_fn:
        st.markdown("<div class='optional'>First name (Optional)</div>", unsafe_allow_html=True)
        first = st.text_input("", placeholder="First name", key="dlg_fn", label_visibility="collapsed")
    with col_ln:
        st.markdown("<div class='optional'>Last name (Optional)</div>", unsafe_allow_html=True)
        last = st.text_input("", placeholder="Last name", key="dlg_ln", label_visibility="collapsed")

    st.markdown("<div class='input-label'>Username</div>", unsafe_allow_html=True)
    username = st.text_input("", placeholder="Choose a username", key="dlg_user", label_visibility="collapsed")

    st.markdown("<div class='input-label'>Email address</div>", unsafe_allow_html=True)
    email = st.text_input("", placeholder="you@example.com", key="dlg_email", label_visibility="collapsed")

    st.markdown("<div class='input-label'>Password</div>", unsafe_allow_html=True)
    password = st.text_input("", placeholder="••••••••", key="dlg_pw", type="password", label_visibility="collapsed")
    st.caption("Use at least 8 characters with a mix of letters, numbers & symbols.")

    if st.button("Continue", type="primary", use_container_width=True):
        if not all([email, username, password]):
            st.error("Email, username and password are required.")
        elif not re.match(r"[^@]+@[^@]+\.[^@]+", email):
            st.error("Please enter a valid email address.")
        elif len(password) < 8:
            st.error("Password must be at least 8 characters long.")
        else:
            user_id = create_user(username, email, password, first, last or None)
            user_row = get_user_by_username(username)
            user = {k: user_row[k] for k in user_row.keys()} 

            st.session_state.user = dict(user)
            # st.session_state.user_id = user["id"]
            
            st.session_state.logged_in = True
            
            st.success(f"Account created successfully for **{username}**!")
            st.rerun()  # This will close the dialog automatically

    st.markdown("---")
    st.markdown("<p class='footer-text'>Already have an account? <a href='#'>Sign in</a></p>", unsafe_allow_html=True)


# Main function to show the dialog
def show_signup_dialog():
    signup_dialog() 
    
         # This opens the dialog