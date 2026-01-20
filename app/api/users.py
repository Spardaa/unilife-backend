"""
Users API - User management
"""
from fastapi import APIRouter, HTTPException

from app.schemas.users import UserResponse, UserUpdate, EnergyProfileUpdate

router = APIRouter()


@router.post("/users/register")
async def register_user():
    """Register a new user"""
    raise HTTPException(status_code=501, detail="Not implemented yet")


@router.post("/users/login")
async def login_user():
    """User login"""
    raise HTTPException(status_code=501, detail="Not implemented yet")


@router.get("/users/me", response_model=UserResponse)
async def get_current_user():
    """Get current user information"""
    raise HTTPException(status_code=501, detail="Not implemented yet")


@router.put("/users/me", response_model=UserResponse)
async def update_current_user():
    """Update current user information"""
    raise HTTPException(status_code=501, detail="Not implemented yet")


@router.put("/users/me/energy")
async def update_energy_profile(profile: EnergyProfileUpdate):
    """Update user energy profile"""
    raise HTTPException(status_code=501, detail="Not implemented yet")
