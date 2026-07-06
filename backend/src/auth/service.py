"""
Authentication service for the Crypto Trading Bot application.
Handles user authentication, JWT tokens, and session management.
"""

import json
import uuid
from base64 import urlsafe_b64decode, urlsafe_b64encode
from datetime import UTC, datetime, timedelta
from hashlib import pbkdf2_hmac
from hmac import compare_digest
from hmac import new as hmac_new
from os import urandom

try:
    import jwt
except ModuleNotFoundError:
    jwt = None
try:
    from argon2 import PasswordHasher
    from argon2.exceptions import VerifyMismatchError
except ModuleNotFoundError:
    PasswordHasher = None
    VerifyMismatchError = ValueError
from fastapi import HTTPException, status
from fastapi.security import HTTPBearer
from shared.config.settings import get_settings
from shared.database.connection import get_db_session
from sqlalchemy import func

from auth.models import User, UserSession
from auth.schemas import TokenResponse, UserResponse

settings = get_settings()
security = HTTPBearer()
ph = PasswordHasher() if PasswordHasher is not None else None
PBKDF2_PREFIX = "$argon2id-fallback-pbkdf2"
PBKDF2_ITERATIONS = 260000


class AuthService:
    """Service for handling authentication operations."""

    def __init__(self):
        self.secret_key = self._secret_value(settings.SECRET_KEY)
        self.algorithm = settings.ALGORITHM
        self.access_token_expire_minutes = settings.ACCESS_TOKEN_EXPIRE_MINUTES
        self.refresh_token_expire_days = settings.REFRESH_TOKEN_EXPIRE_DAYS

    @staticmethod
    def _secret_value(value) -> str:
        if hasattr(value, "get_secret_value"):
            return value.get_secret_value()
        return str(value)

    def verify_password(self, plain_password: str, hashed_password: str) -> bool:
        """Verify a password against its hash."""
        if hashed_password.startswith(f"{PBKDF2_PREFIX}$"):
            return self._verify_pbkdf2_password(plain_password, hashed_password)
        if ph is None:
            return False
        try:
            return ph.verify(hashed_password, plain_password)
        except VerifyMismatchError:
            return False

    def get_password_hash(self, password: str) -> str:
        """Generate password hash."""
        if ph is None:
            return self._hash_pbkdf2_password(password)
        return ph.hash(password)

    @staticmethod
    def _hash_pbkdf2_password(password: str) -> str:
        salt = urandom(16).hex()
        digest = pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), PBKDF2_ITERATIONS).hex()
        return f"{PBKDF2_PREFIX}${PBKDF2_ITERATIONS}${salt}${digest}"

    @staticmethod
    def _verify_pbkdf2_password(password: str, hashed_password: str) -> bool:
        try:
            remainder = hashed_password.removeprefix(f"{PBKDF2_PREFIX}$")
            raw_iterations, salt, expected_digest = remainder.split("$", 2)
            iterations = int(raw_iterations)
        except ValueError:
            return False
        digest = pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), iterations).hex()
        return compare_digest(digest, expected_digest)

    def create_access_token(self, data: dict, expires_delta: timedelta | None = None) -> str:
        """Create access token."""
        to_encode = data.copy()
        issued_at = datetime.now(UTC)
        if expires_delta:
            expire = issued_at + expires_delta
        else:
            expire = issued_at + timedelta(minutes=self.access_token_expire_minutes)

        to_encode.update(
            {
                "exp": expire,
                "iat": issued_at,
                "jti": str(uuid.uuid4()),
                "type": "access",
            }
        )
        if jwt is None:
            return self._encode_fallback_jwt(to_encode)
        encoded_jwt = jwt.encode(to_encode, self.secret_key, algorithm=self.algorithm)
        return encoded_jwt

    def create_refresh_token(self, data: dict) -> str:
        """Create refresh token."""
        to_encode = data.copy()
        issued_at = datetime.now(UTC)
        expire = issued_at + timedelta(days=self.refresh_token_expire_days)
        to_encode.update(
            {
                "exp": expire,
                "iat": issued_at,
                "jti": str(uuid.uuid4()),
                "type": "refresh",
            }
        )
        if jwt is None:
            return self._encode_fallback_jwt(to_encode)
        encoded_jwt = jwt.encode(to_encode, self.secret_key, algorithm=self.algorithm)
        return encoded_jwt

    def verify_token(self, token: str, token_type: str = "access") -> dict:  # noqa: S107
        """Verify and decode token."""
        if jwt is None:
            try:
                payload = self._decode_fallback_jwt(token)
                if payload.get("type") != token_type:
                    raise ValueError("Invalid token type")
                return payload
            except ValueError:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Could not validate credentials",
                    headers={"WWW-Authenticate": "Bearer"},
                ) from None
        try:
            payload = jwt.decode(token, self.secret_key, algorithms=[self.algorithm])
            if payload.get("type") != token_type:
                raise jwt.InvalidTokenError("Invalid token type")
            return payload
        except jwt.PyJWTError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Could not validate credentials",
                headers={"WWW-Authenticate": "Bearer"},
            ) from None

    def _encode_fallback_jwt(self, payload: dict) -> str:
        header = {"alg": "HS256", "typ": "JWT"}
        clean_payload = {
            key: int(value.timestamp()) if isinstance(value, datetime) else value for key, value in payload.items()
        }
        signing_input = ".".join(
            [
                self._base64url_json(header),
                self._base64url_json(clean_payload),
            ]
        )
        signature = hmac_new(
            self.secret_key.encode("utf-8"),
            signing_input.encode("ascii"),
            "sha256",
        ).digest()
        return f"{signing_input}.{self._base64url_bytes(signature)}"

    def _decode_fallback_jwt(self, token: str) -> dict:
        try:
            header_part, payload_part, signature_part = token.split(".", 2)
            signing_input = f"{header_part}.{payload_part}"
            expected_signature = hmac_new(
                self.secret_key.encode("utf-8"),
                signing_input.encode("ascii"),
                "sha256",
            ).digest()
            if not compare_digest(self._base64url_bytes(expected_signature), signature_part):
                raise ValueError("Invalid signature")
            header = json.loads(self._base64url_decode(header_part))
            if header.get("alg") != "HS256":
                raise ValueError("Invalid algorithm")
            payload = json.loads(self._base64url_decode(payload_part))
            exp = payload.get("exp")
            if isinstance(exp, int | float) and datetime.now(UTC).timestamp() > exp:
                raise ValueError("Expired token")
            return payload
        except (ValueError, json.JSONDecodeError):
            raise ValueError("Invalid token") from None

    @staticmethod
    def _base64url_json(value: dict) -> str:
        return AuthService._base64url_bytes(json.dumps(value, separators=(",", ":")).encode("utf-8"))

    @staticmethod
    def _base64url_bytes(value: bytes) -> str:
        return urlsafe_b64encode(value).rstrip(b"=").decode("ascii")

    @staticmethod
    def _base64url_decode(value: str) -> str:
        padding = "=" * (-len(value) % 4)
        return urlsafe_b64decode(f"{value}{padding}").decode("utf-8")

    def authenticate_user(self, username: str, password: str) -> User | None:
        """Authenticate user with username/email and password."""
        identifier = username.strip()
        email_identifier = identifier.lower()
        with get_db_session() as session:
            # Try to find user by username or email
            user = (
                session.query(User)
                .filter((User.username == identifier) | (func.lower(User.email) == email_identifier))
                .first()
            )

            if not user:
                return None

            if not self.verify_password(password, user.hashed_password):
                return None

            if not user.is_active:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Inactive user")

            user.last_active_at = datetime.now(UTC)
            session.commit()

            # Recharger les attributs (session.commit() les a expires en SQLAlchemy 2.0)
            # avant de detacher l'objet, sinon l'appelant declenche une lazy-load sur un
            # objet detache -> "Instance is not bound to a Session".
            session.refresh(user)
            session.expunge(user)
            return user

    def create_user_tokens(self, user: User, ip_address: str, user_agent: str) -> TokenResponse:
        """Create access and refresh tokens for user."""
        # Create token data
        token_data = {
            "sub": user.id,
            "username": user.username,
            "email": user.email,
            "is_admin": user.is_admin,
        }

        # Generate tokens
        access_token = self.create_access_token(token_data)
        refresh_token = self.create_refresh_token({"sub": user.id})

        # Create user response object while we have access to user data
        user_response = UserResponse(
            id=user.id,
            email=user.email,
            username=user.username,
            first_name=user.first_name,
            last_name=user.last_name,
            is_active=user.is_active,
            is_admin=user.is_admin,
            created_at=user.created_at,
            updated_at=user.updated_at,
        )

        # Store refresh token in database
        with get_db_session() as session:
            db_session = UserSession(
                id=str(uuid.uuid4()),
                user_id=user.id,
                token=refresh_token,
                expires_at=datetime.now(UTC) + timedelta(days=self.refresh_token_expire_days),
                ip_address=ip_address,
                user_agent=user_agent,
            )
            session.add(db_session)

        return TokenResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            token_type="bearer",  # noqa: S106
            expires_in=self.access_token_expire_minutes * 60,
            user=user_response,
        )

    def refresh_access_token(self, refresh_token: str) -> str:
        """Generate new access token from refresh token."""
        # Verify refresh token
        payload = self.verify_token(refresh_token, "refresh")
        user_id = payload.get("sub")

        if not user_id:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token")

        # Check if refresh token exists in database
        with get_db_session() as session:
            db_session = (
                session.query(UserSession)
                .filter(
                    UserSession.token == refresh_token,
                    UserSession.expires_at > datetime.now(UTC),
                )
                .first()
            )

            if not db_session:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid or expired refresh token",
                )

            # Get user
            user = session.query(User).filter(User.id == user_id).first()
            if not user or not user.is_active:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="User not found or inactive",
                )

            # Create new access token
            token_data = {
                "sub": user.id,
                "username": user.username,
                "email": user.email,
                "is_admin": user.is_admin,
            }

            return self.create_access_token(token_data)

    def logout_user(self, refresh_token: str) -> bool:
        """Logout user by invalidating refresh token."""
        with get_db_session() as session:
            db_session = session.query(UserSession).filter(UserSession.token == refresh_token).first()

            if db_session:
                session.delete(db_session)
                return True
            return False

    def logout_all_sessions(self, user_id: str) -> int:
        """Logout user from all sessions."""
        with get_db_session() as session:
            count = session.query(UserSession).filter(UserSession.user_id == user_id).delete()
            return count

    def get_current_user(self, token: str) -> User:
        """Get current user from access token."""
        payload = self.verify_token(token)
        user_id = payload.get("sub")

        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Could not validate credentials",
            )

        with get_db_session() as session:
            user = session.query(User).filter(User.id == user_id).first()
            if not user:
                raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")

            if not user.is_active:
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Inactive user")

            user.last_active_at = datetime.now(UTC)
            session.commit()

            # Recharger les attributs (session.commit() les a expires en SQLAlchemy 2.0)
            # avant de detacher l'objet, sinon l'appelant declenche une lazy-load sur un
            # objet detache -> "Instance is not bound to a Session".
            session.refresh(user)
            session.expunge(user)
            return user


# Global auth service instance
auth_service = AuthService()
