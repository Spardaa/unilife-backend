"""
Token Service - JWT token generation and verification
"""
from typing import Dict, Any, Optional
from datetime import datetime, timedelta
from jose import jwt, JWTError

from app.config import settings


class TokenService:
    """Service for JWT token operations"""

    def __init__(self):
        self.secret_key = settings.jwt_secret_key
        self.algorithm = settings.jwt_algorithm
        self.access_token_expire_minutes = settings.jwt_expire_minutes
        self.refresh_token_expire_days = 30  # Refresh tokens last 30 days

    def create_access_token(self, user_id: str) -> str:
        """
        Create an access token for the user

        Args:
            user_id: User UUID

        Returns:
            JWT access token
        """
        expire = datetime.utcnow() + timedelta(minutes=self.access_token_expire_minutes)
        payload = {
            "user_id": user_id,
            "token_type": "access",
            "exp": expire
        }
        return jwt.encode(payload, self.secret_key, algorithm=self.algorithm)

    def create_refresh_token(self, user_id: str) -> str:
        """
        Create a refresh token for the user

        Args:
            user_id: User UUID

        Returns:
            JWT refresh token
        """
        expire = datetime.utcnow() + timedelta(days=self.refresh_token_expire_days)
        payload = {
            "user_id": user_id,
            "token_type": "refresh",
            "exp": expire
        }
        return jwt.encode(payload, self.secret_key, algorithm=self.algorithm)

    def create_token_pair(self, user_id: str) -> Dict[str, Any]:
        """
        Create both access and refresh tokens

        Args:
            user_id: User UUID

        Returns:
            Dictionary with access_token, refresh_token, and expires_in
        """
        access_token = self.create_access_token(user_id)
        refresh_token = self.create_refresh_token(user_id)

        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "expires_in": self.access_token_expire_minutes * 60
        }

    def verify_token(self, token: str) -> Optional[Dict[str, Any]]:
        """
        Verify and decode a JWT token

        Args:
            token: JWT token string

        Returns:
            Decoded token payload if valid, None otherwise
        """
        try:
            payload = jwt.decode(
                token,
                self.secret_key,
                algorithms=[self.algorithm]
            )
            return payload
        except JWTError:
            # Token is invalid or expired
            return None

    def verify_access_token(self, token: str) -> Optional[str]:
        """
        Verify an access token and return user_id

        Args:
            token: JWT access token

        Returns:
            User ID if valid, None otherwise
        """
        payload = self.verify_token(token)
        if payload and payload.get("token_type") == "access":
            return payload.get("user_id")
        return None

    def verify_refresh_token(self, token: str) -> Optional[str]:
        """
        Verify a refresh token and return user_id

        Args:
            token: JWT refresh token

        Returns:
            User ID if valid, None otherwise
        """
        payload = self.verify_token(token)
        if payload and payload.get("token_type") == "refresh":
            return payload.get("user_id")
        return None

    def refresh_access_token(self, refresh_token: str) -> Optional[Dict[str, Any]]:
        """
        Use a refresh token to get a new access token

        Args:
            refresh_token: Valid refresh token

        Returns:
            New token pair if refresh token is valid, None otherwise
        """
        user_id = self.verify_refresh_token(refresh_token)
        if user_id:
            return self.create_token_pair(user_id)
        return None


# Global token service instance
token_service = TokenService()
