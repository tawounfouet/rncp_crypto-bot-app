import re

import streamlit as st


def is_valid_email(email):
    """Check if the provided email is valid using regex."""
    email_regex = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
    return re.match(email_regex, email) is not None


def signup_page(auth_manager):
    """Render the signup page with registration via backend API."""
    if st.button("Back to Login"):
        st.session_state["page"] = "login"
        st.rerun()

    with st.empty().container(border=True):
        st.title("Sign Up Page")

        email = st.text_input("Email")
        if email and not is_valid_email(email):
            st.error("Please enter a valid email address")

        username = st.text_input("Username")
        first_name = st.text_input("First Name (optional)")
        last_name = st.text_input("Last Name (optional)")

        password = st.text_input("Password", type="password")
        confirm_password = st.text_input("Confirm Password", type="password")

        if password and confirm_password and password != confirm_password:
            st.error("Passwords do not match")

        if st.button("Register"):
            if not email or not username or not password:
                st.error("Please fill in email, username and password")
            elif not is_valid_email(email):
                st.error("Please enter a valid email address")
            elif password != confirm_password:
                st.error("Passwords do not match")
            else:
                with st.spinner("Creating account..."):
                    success, message = auth_manager.register(
                        email=email,
                        username=username,
                        password=password,
                        first_name=first_name or None,
                        last_name=last_name or None,
                    )
                if success:
                    st.success("Account created successfully! You are now logged in.")
                    st.session_state["page"] = "app"
                    st.rerun()
                else:
                    st.error(message)
