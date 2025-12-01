# signin.py
import streamlit as st
import streamlit_antd_components as sac
from data_base.database import get_user_by_username, get_user_by_email, verify_password

def show_signin_dialog():
    @st.dialog(title="Sign in to Novachat", width="stretch")
    def _dialog():
        st.markdown("""
        <style>
            .oauth-btn {display:flex;align-items:center;justify-content:center;gap:10px;
                        border:1px solid #e2e8f0;background:#fff;color:#333;border-radius:8px;
                        padding:0.6rem;font-weight:500;width:100%;}
            .oauth-btn:hover {background:#f8f9fa;}
            .input-label {font-size:0.95rem;font-weight:500;color:#1b212c;margin-bottom:0.25rem;}
            .footer-link {text-align:center;color:#95a3c8;font-size:0.85rem;margin-top:1.5rem;}
        </style>
        """, unsafe_allow_html=True)

        st.markdown("**Welcome back! Please sign in to continue.**")

        st.markdown("<div class='input-label'>Email or username</div>", unsafe_allow_html=True)
        identifier = st.text_input(
            "", placeholder="you@example.com or username",
            key="signin_identifier", label_visibility="collapsed"
        )

        st.markdown("<div class='input-label'>Password</div>", unsafe_allow_html=True)
        password = st.text_input(
            "", placeholder="Enter your password",
            key="signin_password", type="password", label_visibility="collapsed"
        )

        if st.button("Continue", type="primary", use_container_width=True, key="signin_continue"):
            if not identifier or not password:
                st.error("Email/username and password are required.")
                return
            user_row = get_user_by_username(identifier) or get_user_by_email(identifier)
            if not user_row:
                st.error("Invalid username/email or password.")
            elif not verify_password(user_row["password_hash"], password):
                st.error("Invalid username/email or password.")
            else:
                user = {k: user_row[k] for k in user_row.keys()}

                st.session_state.user = user
                # st.session_state.user_id = user["User_id"]
                st.session_state.logged_in = True
    
                st.success("Login successful!")
                st.session_state._close_dialog = True   # flag to close instantly
                st.rerun()

        st.markdown("---")
        st.markdown(
            "<p class='footer-link'>Don't have an account? <a href='#'>Sign up</a></p>",
            unsafe_allow_html=True
        )

    _dialog()

    # Close dialog when flag is set
    if st.session_state.get("_close_dialog"):
        del st.session_state._close_dialog