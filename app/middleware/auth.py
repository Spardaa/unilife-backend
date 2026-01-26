"""
Authentication Middleware - JWT validation for protected routes
"""
from typing import Optional
from fastapi import HTTPException, Depends, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from starlette.requests import Request

from app.services.token_service import token_service


# HTTP Bearer token scheme
security = HTTPBearer(auto_error=False)


class AuthMiddleware:
    """Authentication middleware for protected routes"""

    @staticmethod
    async def get_current_user_optional(
        request: Request,
        credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)
    ) -> Optional[str]:
        """
        Get current user from token (optional - returns None if not authenticated)

        Args:
            request: FastAPI request
            credentials: HTTP Bearer credentials

        Returns:
            User ID if token is valid, None otherwise
        """
        if credentials is None:
            return None

        token = credentials.credentials
        user_id = token_service.verify_access_token(token)

        # Store user_id in request state for downstream use
        if user_id:
            request.state.user_id = user_id

        return user_id

    @staticmethod
    async def get_current_user(
        request: Request,
        credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)
    ) -> str:
        """
        Get current user from token (required - raises exception if not authenticated)

        Args:
            request: FastAPI request
            credentials: HTTP Bearer credentials

        Returns:
            User ID

        Raises:
            HTTPException: If token is missing or invalid
        """
        if credentials is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Not authenticated",
                headers={"WWW-Authenticate": "Bearer"},
            )

        token = credentials.credentials
        user_id = token_service.verify_access_token(token)

        if user_id is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired token",
                headers={"WWW-Authenticate": "Bearer"},
            )

        # Store user_id in request state for downstream use
        request.state.user_id = user_id

        return user_id


# Dependency functions for route handlers
async def get_current_user_optional(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)
) -> Optional[str]:
    """Optional authentication - returns None if not authenticated"""
    return await AuthMiddleware.get_current_user_optional(request, credentials)


async def get_current_user(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)
) -> str:
    """Required authentication - raises exception if not authenticated"""
    return await AuthMiddleware.get_current_user(request, credentials)


async def get_user_id_from_state(request: Request) -> Optional[str]:
    """
    Get user_id from request state (if already authenticated by middleware)

    This is a lightweight alternative for endpoints that have already
    gone through authentication.

    Args:
        request: FastAPI request

    Returns:
        User ID from state or None
    """
    return getattr(request.state, "user_id", None)
