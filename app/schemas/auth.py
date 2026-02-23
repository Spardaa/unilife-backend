"""
Authentication Schemas - Request/Response models for auth endpoints
"""
from typing import Optional
from pydantic import BaseModel, Field


class RegisterRequest(BaseModel):
    """User registration request"""
    nickname: str = Field(..., min_length=1, max_length=50, description="User nickname")
    user_id: Optional[str] = Field(None, description="User ID (unique identifier)")
    email: Optional[str] = Field(None, description="User email")
    timezone: str = Field(default="Asia/Shanghai", description="User timezone")

    class Config:
        json_schema_extra = {
            "example": {
                "nickname": "Alex",
                "user_id": "user_abc123",
                "email": "user@example.com",
                "timezone": "Asia/Shanghai"
            }
        }


class LoginRequest(BaseModel):
    """User login request"""
    user_id: str = Field(..., min_length=1, description="User ID")
    email: Optional[str] = Field(None, description="User email (optional, used for account recovery)")
    nickname: Optional[str] = Field(None, description="User nickname (optional, used for new registration)")

    class Config:
        json_schema_extra = {
            "example": {
                "user_id": "user_abc123",
                "email": "user@example.com",
                "nickname": "Alex"
            }
        }


class RefreshTokenRequest(BaseModel):
    """Refresh token request"""
    refresh_token: str = Field(..., description="Refresh token")

    class Config:
        json_schema_extra = {
            "example": {
                "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
            }
        }


class AuthResponse(BaseModel):
    """Authentication response"""
    user_id: str = Field(..., description="User UUID")
    access_token: str = Field(..., description="JWT access token")
    refresh_token: str = Field(..., description="JWT refresh token")
    expires_in: int = Field(..., description="Access token expiration in seconds")

    class Config:
        json_schema_extra = {
            "example": {
                "user_id": "550e8400-e29b-41d4-a716-446655440000",
                "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
                "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
                "expires_in": 604800
            }
        }


class TokenPayload(BaseModel):
    """JWT token payload"""
    user_id: str = Field(..., description="User UUID")
    token_type: str = Field(..., description="Token type: access or refresh")
    exp: int = Field(..., description="Expiration timestamp")
