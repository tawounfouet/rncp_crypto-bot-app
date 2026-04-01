"""
Security configuration for the Crypto Trading Bot.
Handles authentication, authorization, and secret management.
"""

import hashlib
import os
import secrets
from datetime import datetime, timedelta
from typing import Any


class SecurityConfig:
    """Security configuration and utilities."""

    # Default settings
    DEFAULT_SECRET_KEY = "your-secret-key-change-this-in-production"  # noqa: S105
    DEFAULT_ALGORITHM = "HS256"
    DEFAULT_TOKEN_EXPIRE_MINUTES = 30
    DEFAULT_REFRESH_TOKEN_EXPIRE_DAYS = 7

    def __init__(self):
        self.secret_key = self._get_secret_key()
        self.algorithm = os.getenv("ALGORITHM", self.DEFAULT_ALGORITHM)
        self.access_token_expire_minutes = int(
            os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", self.DEFAULT_TOKEN_EXPIRE_MINUTES)
        )
        self.refresh_token_expire_days = int(
            os.getenv("REFRESH_TOKEN_EXPIRE_DAYS", self.DEFAULT_REFRESH_TOKEN_EXPIRE_DAYS)
        )

    def _get_secret_key(self) -> str:
        """Get or generate secret key."""
        secret_key = os.getenv("SECRET_KEY")

        if not secret_key:
            # Generate a secure random key
            secret_key = secrets.token_urlsafe(32)
            print(f"Warning: No SECRET_KEY found in environment. Generated temporary key: {secret_key}")
            print("Please set SECRET_KEY environment variable for production use.")

        return secret_key

    def hash_password(self, password: str) -> str:
        """Hash a password using basic hashlib (bcrypt would be better but requires dependency)."""
        salt = secrets.token_hex(16)
        hashed = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), 100000)
        return f"{salt}${hashed.hex()}"

    def verify_password(self, password: str, hashed_password: str) -> bool:
        """Verify a password against its hash."""
        try:
            salt, stored_hash = hashed_password.split("$")
            hashed = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), 100000)
            return hashed.hex() == stored_hash
        except Exception:
            return False

    def create_token_payload(self, data: dict[str, Any], token_type: str, expire_delta: timedelta) -> dict[str, Any]:
        """Create token payload."""
        to_encode = data.copy()
        expire = datetime.utcnow() + expire_delta
        to_encode.update({"exp": expire, "type": token_type})
        return to_encode

    def create_access_token(self, data: dict[str, Any]) -> str:
        """Create JWT access token (simplified - requires PyJWT for production)."""
        payload = self.create_token_payload(data, "access", timedelta(minutes=self.access_token_expire_minutes))
        # For now, return a simple token format (replace with JWT in production)
        import base64
        import json

        token_data = json.dumps(payload, default=str)
        return base64.b64encode(token_data.encode()).decode()

    def create_refresh_token(self, data: dict[str, Any]) -> str:
        """Create JWT refresh token (simplified)."""
        payload = self.create_token_payload(data, "refresh", timedelta(days=self.refresh_token_expire_days))
        # For now, return a simple token format (replace with JWT in production)
        import base64
        import json

        token_data = json.dumps(payload, default=str)
        return base64.b64encode(token_data.encode()).decode()

    def verify_token(
        self,
        token: str,
        token_type: str = "access",  # noqa: S107
    ) -> dict[str, Any] | None:
        """Verify and decode token (simplified)."""
        try:
            import base64
            import json
            from datetime import datetime

            token_data = base64.b64decode(token.encode()).decode()
            payload = json.loads(token_data)

            # Check expiration
            exp_str = payload.get("exp")
            if exp_str:
                exp_time = datetime.fromisoformat(exp_str.replace("Z", "+00:00").replace("+00:00", ""))
                if datetime.utcnow() > exp_time:
                    return None

            # Check token type
            if payload.get("type") != token_type:
                return None

            return payload
        except Exception:
            return None

    def generate_api_key(self) -> str:
        """Generate a secure API key."""
        return secrets.token_urlsafe(32)

    def hash_api_key(self, api_key: str) -> str:
        """Hash an API key for storage."""
        return hashlib.sha256(api_key.encode()).hexdigest()

    def verify_api_key(self, api_key: str, hashed_api_key: str) -> bool:
        """Verify an API key against its hash."""
        return self.hash_api_key(api_key) == hashed_api_key


class RateLimiter:
    """Simple in-memory rate limiter."""

    def __init__(self, max_requests: int = 100, window_seconds: int = 60):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.requests = {}  # {client_id: [timestamp, ...]}

    def is_allowed(self, client_id: str) -> bool:
        """Check if request is allowed for client."""
        now = datetime.now()
        window_start = now - timedelta(seconds=self.window_seconds)

        # Clean old requests
        if client_id in self.requests:
            self.requests[client_id] = [req_time for req_time in self.requests[client_id] if req_time > window_start]
        else:
            self.requests[client_id] = []

        # Check if under limit
        if len(self.requests[client_id]) < self.max_requests:
            self.requests[client_id].append(now)
            return True

        return False

    def get_remaining_requests(self, client_id: str) -> int:
        """Get remaining requests for client."""
        if client_id not in self.requests:
            return self.max_requests

        return max(0, self.max_requests - len(self.requests[client_id]))


# Global security config instance
security_config = SecurityConfig()

# Global rate limiter
rate_limiter = RateLimiter(
    max_requests=int(os.getenv("RATE_LIMIT_REQUESTS", "100")),
    window_seconds=int(os.getenv("RATE_LIMIT_WINDOW", "60")),
)


# Convenience functions
def hash_password(password: str) -> str:
    """Hash a password."""
    return security_config.hash_password(password)


def verify_password(password: str, hashed_password: str) -> bool:
    """Verify a password."""
    return security_config.verify_password(password, hashed_password)


def create_access_token(data: dict[str, Any]) -> str:
    """Create access token."""
    return security_config.create_access_token(data)


def create_refresh_token(data: dict[str, Any]) -> str:
    """Create refresh token."""
    return security_config.create_refresh_token(data)


def verify_token(token: str, token_type: str = "access") -> dict[str, Any] | None:  # noqa: S107
    """Verify token."""
    return security_config.verify_token(token, token_type)


def generate_api_key() -> str:
    """Generate API key."""
    return security_config.generate_api_key()


def check_rate_limit(client_id: str) -> bool:
    """Check rate limit for client."""
    return rate_limiter.is_allowed(client_id)
