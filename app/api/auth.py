"""
Authentication API - Register, Login, and Token Refresh endpoints
"""
from fastapi import APIRouter, HTTPException, status
from datetime import datetime

from app.schemas.auth import (
    RegisterRequest, LoginRequest, RefreshTokenRequest, AuthResponse
)
from app.services.token_service import token_service
from app.services.db import db_service


router = APIRouter(prefix="/api/v1/auth", tags=["Authentication"])


@router.post("/register", response_model=AuthResponse, status_code=status.HTTP_201_CREATED)
async def register(request: RegisterRequest):
    """
    Register a new user

    Creates a new user account and returns access/refresh tokens.
    If a user with the same user_id already exists, returns existing user's tokens.
    """
    # Check if user already exists by user_id
    existing_user = None
    if request.user_id:
        existing_user = await db_service.get_user_by_user_id(request.user_id)

    if existing_user:
        # User exists - return tokens for existing user
        db_user_id = existing_user["id"]

        # Update last_active_at (use datetime object directly)
        await db_service.update_user(db_user_id, {"last_active_at": datetime.utcnow()})

        tokens = token_service.create_token_pair(db_user_id)
        return AuthResponse(
            user_id=db_user_id,
            **tokens
        )

    # Create new user
    user_data = request.model_dump()

    # Set timestamps (use datetime objects directly, not ISO strings)
    user_data["created_at"] = datetime.utcnow()
    user_data["last_active_at"] = datetime.utcnow()

    # Create user in database
    new_user = await db_service.create_user(user_data)
    db_user_id = new_user["id"]

    # Generate tokens
    tokens = token_service.create_token_pair(db_user_id)

    return AuthResponse(
        user_id=db_user_id,
        **tokens
    )


@router.post("/login", response_model=AuthResponse)
async def login(request: LoginRequest):
    """
    Login with User ID

    Authenticates a user using their user ID and returns access/refresh tokens.
    If the user doesn't exist, they will be auto-registered.
    """
    # Try to find existing user by Apple user_id
    existing_user = await db_service.get_user_by_user_id(request.user_id)

    if existing_user:
        # User exists - update last_active_at and return tokens
        db_user_id = existing_user["id"]
        update_data = {"last_active_at": datetime.utcnow()}
        # Save email/nickname if they were not set before
        if request.email and not existing_user.get("email"):
            update_data["email"] = request.email
        if request.nickname and existing_user.get("nickname") == existing_user.get("user_id"):
            update_data["nickname"] = request.nickname
            
        await db_service.update_user(db_user_id, update_data)

        tokens = token_service.create_token_pair(db_user_id)
        return AuthResponse(
            user_id=db_user_id,
            **tokens
        )
        
    # User not found by user_id. Check if we can find them by email.
    if request.email:
        from app.services.db import UserModel
        db_service._ensure_initialized()
        with db_service.get_session() as session:
            user_by_email = session.query(UserModel).filter(UserModel.email == request.email).first()
            if user_by_email:
                db_user_id = user_by_email.id
                
                # We found an old account with the same email! 
                # Update their Apple user_id to the new one, so next time it finds them by user_id
                user_by_email.user_id = request.user_id
                user_by_email.last_active_at = datetime.utcnow()
                if request.nickname and user_by_email.nickname == user_by_email.user_id:
                    user_by_email.nickname = request.nickname
                
                session.commit()
                
                tokens = token_service.create_token_pair(db_user_id)
                return AuthResponse(
                    user_id=db_user_id,
                    **tokens
                )

    # Auto-register new user
    user_data = {
        "user_id": request.user_id,
        "email": request.email,
        "nickname": request.nickname or request.user_id,  # Default to user_id if no nickname
        "timezone": "Asia/Shanghai",
        "created_at": datetime.utcnow(),
        "last_active_at": datetime.utcnow()
    }

    new_user = await db_service.create_user(user_data)
    db_user_id = new_user["id"]

    tokens = token_service.create_token_pair(db_user_id)

    return AuthResponse(
        user_id=db_user_id,
        **tokens
    )


@router.post("/refresh", response_model=AuthResponse)
async def refresh_token(request: RefreshTokenRequest):
    """
    Refresh access token using refresh token

    Returns a new pair of access and refresh tokens.
    The old refresh token is invalidated.
    """
    # Verify refresh token and get new tokens
    new_tokens = token_service.refresh_access_token(request.refresh_token)

    if new_tokens is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token"
        )

    # Extract user_id from refresh token (already verified in refresh_access_token)
    from app.services.token_service import token_service as ts
    payload = ts.verify_token(request.refresh_token)
    user_id = payload["user_id"] if payload else None

    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload"
        )

    return AuthResponse(
        user_id=user_id,
        **new_tokens
    )
