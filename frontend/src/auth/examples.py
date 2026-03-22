"""
Example usage of authentication utilities for Streamlit.

This module demonstrates how to integrate the auth utilities
with existing Streamlit login/signup pages.
"""

import streamlit as st
from auth.auth_manager import AuthManager
from auth.utils import validate_email, validate_password_strength, format_user_display


def example_login_page():
    """
    Example login page using AuthManager.
    Replace the existing login_page() function with this implementation.
    """
    st.title("Login Page")

    # Initialize AuthManager
    auth_manager = AuthManager()

    # Check API health
    is_healthy, health_msg = auth_manager.check_health()
    if not is_healthy:
        st.error(f"⚠️ API is not available: {health_msg}")
        st.info("Please make sure the backend server is running on http://localhost:8009")
        return

    # Login form
    with st.form("login_form"):
        username = st.text_input("Username or Email")
        password = st.text_input("Password", type="password")

        col1, col2 = st.columns(2)
        with col1:
            login_button = st.form_submit_button("Login")
        with col2:
            use_json = st.checkbox("Use JSON format", value=True)

        if login_button:
            if not (username and password):
                st.error("Please provide username and password")
            else:
                with st.spinner("Logging in..."):
                    success, message = auth_manager.login(username, password, use_json=use_json)

                if success:
                    st.success(message)
                    # Get user data
                    user_success, user_data = auth_manager.get_current_user()
                    if user_success:
                        st.info(f"Welcome back, {user_data.get('username', 'User')}!")

                    # Redirect to app page
                    st.session_state["page"] = "app"
                    st.rerun()
                else:
                    st.error(message)

    # Sign up link
    if st.button("Sign Up"):
        st.session_state["page"] = "signup"
        st.rerun()

    # Guest mode
    if st.button("Continue as Guest"):
        st.session_state["guest_mode"] = True
        st.session_state["authenticated"] = True
        st.session_state["page"] = "app"
        st.rerun()


def example_signup_page():
    """
    Example signup page using AuthManager.
    Replace the existing signup_page() function with this implementation.
    """
    st.title("Sign Up Page")

    # Initialize AuthManager
    auth_manager = AuthManager()

    # Check API health
    is_healthy, health_msg = auth_manager.check_health()
    if not is_healthy:
        st.warning(f"⚠️ API is not available: {health_msg}")

    with st.form("signup_form"):
        email = st.text_input("Email")
        username = st.text_input("Username")
        first_name = st.text_input("First Name (optional)")
        last_name = st.text_input("Last Name (optional)")
        password = st.text_input("Password", type="password")
        confirm_password = st.text_input("Confirm Password", type="password")

        submit_button = st.form_submit_button("Register")

        if submit_button:
            # Validate inputs
            if not (email and username and password):
                st.error("Email, username, and password are required")
            elif not validate_email(email):
                st.error("Please enter a valid email address")
            elif password != confirm_password:
                st.error("Passwords do not match")
            else:
                # Validate password strength
                is_strong, pwd_message = validate_password_strength(password)
                if not is_strong:
                    st.error(pwd_message)
                else:
                    # Register user
                    with st.spinner("Registering..."):
                        success, message = auth_manager.register(
                            email=email,
                            username=username,
                            password=password,
                            first_name=first_name if first_name else None,
                            last_name=last_name if last_name else None,
                        )

                    if success:
                        st.success(message)
                        st.info("You are now logged in!")
                        # Redirect to app page
                        st.session_state["page"] = "app"
                        st.rerun()
                    else:
                        st.error(message)

    # Back to login
    if st.button("Back to Login"):
        st.session_state["page"] = "login"
        st.rerun()


def example_user_profile():
    """
    Example user profile display.
    Use this in your app page to show user information.
    """
    auth_manager = AuthManager()

    if not auth_manager.is_authenticated():
        st.warning("Please login to view your profile")
        return

    st.subheader("User Profile")

    # Get current user data
    success, user_data = auth_manager.get_current_user()

    if success and user_data:
        st.markdown(format_user_display(user_data))

        # Logout buttons
        col1, col2 = st.columns(2)
        with col1:
            if st.button("Logout"):
                success, message = auth_manager.logout()
                if success:
                    st.success(message)
                    st.session_state["page"] = "login"
                    st.rerun()
                else:
                    st.error(message)

        with col2:
            if st.button("Logout All Sessions"):
                success, message = auth_manager.logout_all_sessions()
                if success:
                    st.success(message)
                    st.session_state["page"] = "login"
                    st.rerun()
                else:
                    st.error(message)
    else:
        st.error("Failed to load user data")
        if st.button("Try to refresh token"):
            success, message = auth_manager.refresh_access_token()
            if success:
                st.success(message)
                st.rerun()
            else:
                st.error(message)


def example_protected_endpoint():
    """
    Example of how to protect a page/endpoint with authentication.
    """
    auth_manager = AuthManager()

    if not auth_manager.is_authenticated():
        st.error("⚠️ You must be logged in to access this page")
        if st.button("Go to Login"):
            st.session_state["page"] = "login"
            st.rerun()
        return

    # Protected content here
    st.success("✅ You have access to this protected content")

    # Your protected page content...
    st.write("This is a protected page that requires authentication")
