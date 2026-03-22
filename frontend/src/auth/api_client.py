"""
API Client for authentication operations.
Based on notebook: 01_auth_endpoints_testing.ipynb
"""

import requests
import urllib.parse
from typing import Dict, Any, Optional
from .config import (
    AUTH_URL,
    USERS_URL,
    DEFAULT_HEADERS,
    OAUTH2_HEADERS,
    REQUEST_TIMEOUT,
)


class APIResponse:
    """Standardized API response wrapper."""

    def __init__(self, status_code: int, data: Any = None, error: Optional[str] = None):
        self.status_code = status_code
        self.data = data
        self.error = error
        self.success = status_code < 400

    def __repr__(self):
        return f"APIResponse(status={self.status_code}, success={self.success})"


class AuthAPIClient:
    """
    Client for interacting with authentication API endpoints.

    Endpoints supported:
    - POST /auth/register - Register new user
    - POST /auth/login - Login with OAuth2 (form-data)
    - POST /auth/login/json - Login with JSON
    - POST /auth/refresh - Refresh access token
    - POST /auth/logout - Logout current session
    - POST /auth/logout-all - Logout all sessions
    - GET /users/me - Get current user info
    """

    def __init__(self, base_url: Optional[str] = None):
        """
        Initialize the API client.

        Args:
            base_url: Optional custom base URL for the API
        """
        self.auth_url = AUTH_URL if base_url is None else f"{base_url}/api/v1/auth"
        self.users_url = USERS_URL if base_url is None else f"{base_url}/api/v1/users"
        self.timeout = REQUEST_TIMEOUT

    def _make_request(
        self,
        method: str,
        url: str,
        data: Optional[Dict] = None,
        headers: Optional[Dict] = None,
        auth_token: Optional[str] = None,
        is_form_data: bool = False,
    ) -> APIResponse:
        """
        Internal method to make HTTP requests.

        Args:
            method: HTTP method (GET, POST, etc.)
            url: Full URL to request
            data: Request payload
            headers: Request headers
            auth_token: Optional Bearer token
            is_form_data: Whether to send data as form-data

        Returns:
            APIResponse object
        """
        # Prepare headers
        req_headers = (headers or DEFAULT_HEADERS).copy()

        # Add authentication token if provided
        if auth_token:
            req_headers["Authorization"] = f"Bearer {auth_token}"

        try:
            # Make the request
            if method.upper() == "GET":
                response = requests.get(url, headers=req_headers, timeout=self.timeout)
            elif method.upper() == "POST":
                if is_form_data:
                    # Send as form-data for OAuth2
                    response = requests.post(url, data=data, headers=req_headers, timeout=self.timeout)
                else:
                    # Send as JSON
                    response = requests.post(url, json=data, headers=req_headers, timeout=self.timeout)
            elif method.upper() == "PUT":
                response = requests.put(url, json=data, headers=req_headers, timeout=self.timeout)
            elif method.upper() == "DELETE":
                response = requests.delete(url, headers=req_headers, timeout=self.timeout)
            else:
                return APIResponse(0, error=f"Unsupported HTTP method: {method}")

            # Parse response
            try:
                response_data = response.json()
            except Exception:
                response_data = response.text

            return APIResponse(status_code=response.status_code, data=response_data)

        except requests.exceptions.Timeout:
            return APIResponse(0, error="Request timeout")
        except requests.exceptions.ConnectionError:
            return APIResponse(0, error="Connection error - is the API server running?")
        except Exception as e:
            return APIResponse(0, error=str(e))

    def register(
        self,
        email: str,
        username: str,
        password: str,
        first_name: Optional[str] = None,
        last_name: Optional[str] = None,
    ) -> APIResponse:
        """
        Register a new user.

        Args:
            email: User email
            username: Username
            password: User password
            first_name: Optional first name
            last_name: Optional last name

        Returns:
            APIResponse with access_token and refresh_token if successful
        """
        data = {"email": email, "username": username, "password": password}

        if first_name:
            data["first_name"] = first_name
        if last_name:
            data["last_name"] = last_name

        return self._make_request("POST", f"{self.auth_url}/register", data)

    def login_oauth2(self, username: str, password: str) -> APIResponse:
        """
        Login with OAuth2 (form-data format).

        Args:
            username: Username or email
            password: User password

        Returns:
            APIResponse with access_token and refresh_token if successful
        """
        form_data = urllib.parse.urlencode({"username": username, "password": password})

        return self._make_request(
            "POST",
            f"{self.auth_url}/login",
            data=form_data,
            headers=OAUTH2_HEADERS,
            is_form_data=True,
        )

    def login_json(self, username: str, password: str) -> APIResponse:
        """
        Login with JSON format.

        Args:
            username: Username or email
            password: User password

        Returns:
            APIResponse with access_token and refresh_token if successful
        """
        data = {"username": username, "password": password}

        return self._make_request("POST", f"{self.auth_url}/login/json", data)

    def refresh_token(self, refresh_token: str) -> APIResponse:
        """
        Refresh access token using refresh token.

        Args:
            refresh_token: Valid refresh token

        Returns:
            APIResponse with new access_token if successful
        """
        url = f"{self.auth_url}/refresh?refresh_token={refresh_token}"
        return self._make_request("POST", url)

    def logout(self, refresh_token: str) -> APIResponse:
        """
        Logout current session.

        Args:
            refresh_token: Refresh token to invalidate

        Returns:
            APIResponse confirming logout
        """
        url = f"{self.auth_url}/logout?refresh_token={refresh_token}"
        return self._make_request("POST", url)

    def logout_all(self, user_id: int) -> APIResponse:
        """
        Logout all sessions for a user.

        Args:
            user_id: User ID

        Returns:
            APIResponse confirming all sessions logged out
        """
        url = f"{self.auth_url}/logout-all?user_id={user_id}"
        return self._make_request("POST", url)

    def get_current_user(self, access_token: str) -> APIResponse:
        """
        Get current user information.

        Args:
            access_token: Valid access token

        Returns:
            APIResponse with user data if successful
        """
        return self._make_request("GET", f"{self.users_url}/me", auth_token=access_token)

    def health_check(self) -> APIResponse:
        """
        Check API health status.

        Returns:
            APIResponse with health status
        """
        # Extract base URL from auth_url
        base_url = self.auth_url.split("/api")[0]
        return self._make_request("GET", f"{base_url}/health")
