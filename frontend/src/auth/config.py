"""
Configuration for API client authentication.
"""

import os

# API Configuration
BASE_URL = os.getenv("API_URL", "http://localhost:8009")
API_PREFIX = "/api/v1"
AUTH_URL = f"{BASE_URL}{API_PREFIX}/auth"
USERS_URL = f"{BASE_URL}{API_PREFIX}/users"

# Default headers
DEFAULT_HEADERS = {"Content-Type": "application/json", "Accept": "application/json"}

# OAuth2 form headers
OAUTH2_HEADERS = {
    "Content-Type": "application/x-www-form-urlencoded",
    "Accept": "application/json",
}

# Timeouts
REQUEST_TIMEOUT = 30  # seconds
