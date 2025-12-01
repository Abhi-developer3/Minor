# change_password.py
import streamlit as st
from data_base.database import get_user_by_id, conn
import hashlib

# Reuse your existing hash function from database.py
def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()

def show_change_password_dialog():
    user = st.session_state.get("user")
    if not user or not user.get("id"):
        st.error("User not logged in.")
        return

    user_id = user["id"]
    current_user = get_user_by_id(user_id)
    stored_hash = current_user["password_hash"] if isinstance(current_user, dict) else current_user["password_hash"]

    @st.dialog(title="Change Password", width="stretch")
    def password_dialog():
        st.markdown("### Update Your Password")
        st.markdown("Keep your account secure with a strong password.")

        with st.form(key="change_password_form"):
            old_password = st.text_input("Current Password", type="password", placeholder="Enter your current password")

            new_password = st.text_input("New Password", type="password", placeholder="Create a strong password")
            
            confirm_password = st.text_input("Confirm New Password", type="password", placeholder="Type it again")

            # Password strength indicator
            if new_password:
                strength = 0
                if len(new_password) >= 8: strength += 1
                if any(c.isupper() for c in new_password): strength += 1
                if any(c.islower() for c in new_password): strength += 1
                if any(c.isdigit() for c in new_password): strength += 1
                if any(c in "!@#$%^&*()_+" for c in new_password): strength += 1

                strength_text = ["Very Weak", "Weak", "Fair", "Good", "Strong"][min(strength-1, 4)]
                color = ["red", "orange", "yellow", "lightgreen", "green"][min(strength-1, 4)]
                st.markdown(f"**Strength:** <span style='color:{color}'>{strength_text}</span>", unsafe_allow_html=True)

            st.divider()

        
            submit = st.form_submit_button("Change Password", type="primary", use_container_width=True)

            if submit:
                errors = False

                # Check current password
                if hash_password(old_password) != stored_hash:
                    st.error("Current password is incorrect.")
                    errors = True

                # Check new password rules
                if len(new_password) < 8:
                    st.error("New password must be at least 8 characters.")
                    errors = True
                if new_password != confirm_password:
                    st.error("New passwords do not match.")
                    errors = True
                if new_password == old_password:
                    st.error("New password must be different from current.")
                    errors = True

                if not errors:
                    try:
                        with conn:
                            conn.execute(
                                "UPDATE users SET password_hash = ? WHERE id = ?",
                                (hash_password(new_password), user_id)
                            )
                        st.success("Password changed successfully!")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Failed to update password: {e}")

        

            


    password_dialog()