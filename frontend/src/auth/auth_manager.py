"""
Authentication Manager for handling auth state in Streamlit.
"""

import streamlit as st
from typing import Optional, Dict, Any, Tuple
from .api_client import AuthAPIClient, APIResponse


class AuthManager:
    """
    Manages authentication state and operations for Streamlit app.

    Handles:
    - Login/logout operations
    - Token storage and refresh
    - User session management
    - Integration with Streamlit session state
    """

    def __init__(self, api_client: Optional[AuthAPIClient] = None):
        """
        Initialize the authentication manager.

        Args:
            api_client: Optional custom API client instance
        """
        self.client = api_client or AuthAPIClient()
        self._init_session_state()

    def _init_session_state(self):
        """Initialize session state variables if they don't exist."""
        if "access_token" not in st.session_state:
            st.session_state["access_token"] = None
        if "refresh_token" not in st.session_state:
            st.session_state["refresh_token"] = None
        if "user_data" not in st.session_state:
            st.session_state["user_data"] = None
        if "authenticated" not in st.session_state:
            st.session_state["authenticated"] = False

    def register(
        self,
        email: str,
        username: str,
        password: str,
        first_name: Optional[str] = None,
        last_name: Optional[str] = None,
    ) -> Tuple[bool, str]:
        """
        Register a new user.

        Args:
            email: User email
            username: Username
            password: Password
            first_name: Optional first name
            last_name: Optional last name

        Returns:
            Tuple of (success: bool, message: str)
        """
        response = self.client.register(email, username, password, first_name, last_name)

        if response.success:
            # Store tokens and authenticate
            self._store_auth_data(response.data)
            return True, "Registration successful!"
        else:
            error_msg = self._extract_error_message(response)
            return False, f"Registration failed: {error_msg}"

    def login(self, username: str, password: str, use_json: bool = True) -> Tuple[bool, str]:
        """
        Login user with credentials.

        Args:
            username: Username or email
            password: Password
            use_json: Use JSON format (True) or OAuth2 format (False)

        Returns:
            Tuple of (success: bool, message: str)
        """
        if use_json:
            response = self.client.login_json(username, password)
        else:
            response = self.client.login_oauth2(username, password)

        if response.success:
            # Store tokens and authenticate
            self._store_auth_data(response.data)
            return True, "Login successful!"
        else:
            error_msg = self._extract_error_message(response)
            return False, f"Login failed: {error_msg}"

    def logout(self) -> Tuple[bool, str]:
        """
        Logout current user.

        Returns:
            Tuple of (success: bool, message: str)
        """
        refresh_token = st.session_state.get("refresh_token")

        if not refresh_token:
            self._clear_auth_data()
            return True, "Logged out successfully"

        response = self.client.logout(refresh_token)
        self._clear_auth_data()

        if response.success:
            return True, "Logged out successfully"
        else:
            # Still clear local data even if server request failed
            return True, "Logged out (local session cleared)"

    def logout_all_sessions(self) -> Tuple[bool, str]:
        """
        Logout all sessions for current user.

        Returns:
            Tuple of (success: bool, message: str)
        """
        user_data = st.session_state.get("user_data")

        if not user_data or "id" not in user_data:
            return False, "No user data available"

        user_id = user_data["id"]
        response = self.client.logout_all(user_id)
        self._clear_auth_data()

        if response.success:
            return True, "All sessions logged out successfully"
        else:
            error_msg = self._extract_error_message(response)
            return False, f"Logout all failed: {error_msg}"

    def refresh_access_token(self) -> Tuple[bool, str]:
        """
        Refresh the access token using refresh token.

        Returns:
            Tuple of (success: bool, message: str)
        """
        refresh_token = st.session_state.get("refresh_token")

        if not refresh_token:
            return False, "No refresh token available"

        response = self.client.refresh_token(refresh_token)

        if response.success:
            # Update access token
            if "access_token" in response.data:
                st.session_state["access_token"] = response.data["access_token"]
            return True, "Token refreshed successfully"
        else:
            error_msg = self._extract_error_message(response)
            return False, f"Token refresh failed: {error_msg}"

    def get_current_user(self) -> Tuple[bool, Optional[Dict[str, Any]]]:
        """
        Get current user information.

        Returns:
            Tuple of (success: bool, user_data: Optional[Dict])
        """
        access_token = st.session_state.get("access_token")

        if not access_token:
            return False, None

        response = self.client.get_current_user(access_token)

        if response.success:
            st.session_state["user_data"] = response.data
            return True, response.data
        else:
            # Token might be expired, try to refresh
            refresh_success, _ = self.refresh_access_token()
            if refresh_success:
                # Retry with new token
                access_token = st.session_state.get("access_token")
                response = self.client.get_current_user(access_token)
                if response.success:
                    st.session_state["user_data"] = response.data
                    return True, response.data

            return False, None

    def is_authenticated(self) -> bool:
        """
        Check if user is authenticated.

        Returns:
            True if user is authenticated, False otherwise
        """
        return st.session_state.get("authenticated", False)

    def check_health(self) -> Tuple[bool, str]:
        """
        Check API health status.

        Returns:
            Tuple of (is_healthy: bool, message: str)
        """
        response = self.client.health_check()

        if response.success:
            return True, "API is healthy"
        else:
            error_msg = self._extract_error_message(response)
            return False, f"API health check failed: {error_msg}"

    def _store_auth_data(self, data: Dict[str, Any]):
        """Store authentication data in session state."""
        if "access_token" in data:
            st.session_state["access_token"] = data["access_token"]
        if "refresh_token" in data:
            st.session_state["refresh_token"] = data["refresh_token"]

        st.session_state["authenticated"] = True

        # Try to fetch user data
        self.get_current_user()

    def _clear_auth_data(self):
        """Clear authentication data from session state."""
        st.session_state["access_token"] = None
        st.session_state["refresh_token"] = None
        st.session_state["user_data"] = None
        st.session_state["authenticated"] = False

    def _extract_error_message(self, response: APIResponse) -> str:
        """Extract error message from API response."""
        if response.error:
            return response.error

        if isinstance(response.data, dict):
            # Try common error message keys
            for key in ["detail", "message", "error"]:
                if key in response.data:
                    return str(response.data[key])

        return f"Status code: {response.status_code}"
