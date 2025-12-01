# edit_profile.py
import streamlit as st
from data_base.database import get_user_by_id, conn
import hashlib


def _gravatar(email, size=100):
    digest = hashlib.md5(email.lower().encode("utf-8")).hexdigest()
    return f"https://www.gravatar.com/avatar/{digest}?d=identicon&s={size}"


def show_edit_profile_dialog():
    """
    Opens a beautiful modal dialog to edit First Name & Last Name
    Call this from your main file exactly like show_view_profile_dialog()
    """
    user = st.session_state.get("user")
    if not user or not user.get("id"):
        st.error("User not logged in.")
        return

    user_id = user["id"]
    fresh_user = get_user_by_id(user_id)
    u = dict(fresh_user) if not isinstance(fresh_user, dict) else fresh_user

    @st.dialog(title="Edit Profile", width="stretch")
    def edit_dialog():
        st.markdown("### Update Your Information")

        # Avatar + Name header
        col1, col2 = st.columns([1, 4])
        with col1:
            st.image(_gravatar(u.get("email", "")), width=90)
        with col2:
            st.markdown(f"**@{u.get('username')}**")
            st.caption(f"Member since {(u.get('created_at') or '').split('.')[0]}")

        st.divider()

        with st.form(key="edit_profile_form"):
            col_fn, col_ln = st.columns(2)
            with col_fn:
                first_name = st.text_input(
                    "First Name", value=u.get("first_name") or "", placeholder="John"
                )
            with col_ln:
                last_name = st.text_input(
                    "Last Name", value=u.get("last_name") or "", placeholder="Doe"
                )

            st.text_input("Email", value=u.get("email"), disabled=True)
            st.info("Email cannot be changed")

            st.text_input("Username", value=u.get("username"), disabled=True)
            st.info("Username cannot be changed")
            save_clicked = st.form_submit_button(
                "Save Changes", type="primary", use_container_width=True
            )

            if save_clicked:
                if not first_name.strip():
                    st.error("First name is required.")
                else:
                    try:
                        with conn:
                            conn.execute(
                                "UPDATE users SET first_name = ?, last_name = ? WHERE id = ?",
                                (
                                    first_name.strip(),
                                    last_name.strip() or None,
                                    user_id,
                                ),
                            )
                        # Update session instantly
                        st.session_state.user["first_name"] = first_name.strip()
                        st.session_state.user["last_name"] = last_name.strip() or None

                        st.success("Profile updated successfully!")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Update failed: {e}")


    # Open the dialog
    edit_dialog()
