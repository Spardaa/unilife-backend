"""
Users API - User management endpoints
"""
from typing import Optional
from datetime import datetime
from fastapi import APIRouter, HTTPException, Depends

from app.schemas.users import (
    UserResponse, UserUpdate, EnergyProfileUpdate,
    UserProfileResponse, UserStatsResponse
)
from app.schemas.notification_settings import NotificationSettings
from app.services.db import db_service
from app.services.profile_service import profile_service
from app.services.decision_profile_service import decision_profile_service
from app.middleware.auth import get_current_user

router = APIRouter()


@router.get("/users/me", response_model=UserResponse)
async def read_users_me(user_id: str = Depends(get_current_user)):
    """
    Get current user information

    Returns basic user profile including energy profile and preferences.
    """
    # Get user by database id (JWT user_id is the database primary key)
    user = await db_service.get_user(user_id)

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    return UserResponse(**user)


@router.put("/users/me", response_model=UserResponse)
async def update_current_user(
    update_data: UserUpdate,
    user_id: str = Depends(get_current_user)
):
    """
    Update current user information

    Supports partial updates - only updates fields that are provided.
    """
    # Build update data with only non-None values
    update_dict = update_data.model_dump(exclude_unset=True)

    if not update_dict:
        raise HTTPException(status_code=400, detail="No fields to update")

    # Update last_active_at
    update_dict["last_active_at"] = datetime.utcnow()

    result = await db_service.update_user(user_id, update_dict)

    if not result:
        raise HTTPException(status_code=404, detail="Failed to update user")

    return UserResponse(**result)


@router.put("/users/me/energy", response_model=UserResponse)
async def update_energy_profile(
    energy_update: EnergyProfileUpdate,
    user_id: str = Depends(get_current_user)
):
    """
    Update user energy configuration

    Updates the energy profile including hourly baseline and task energy costs.
    """
    # Get existing user
    existing = await db_service.get_user(user_id)
    if not existing:
        raise HTTPException(status_code=404, detail="User not found")

    # Merge with existing energy profile
    existing_energy = existing.get("energy_profile", {})

    updated_energy = {
        "hourly_baseline": energy_update.hourly_baseline if energy_update.hourly_baseline is not None else existing_energy.get("hourly_baseline", {}),
        "task_energy_cost": energy_update.task_energy_cost if energy_update.task_energy_cost is not None else existing_energy.get("task_energy_cost", {}),
        "learned_adjustments": energy_update.learned_adjustments if energy_update.learned_adjustments is not None else existing_energy.get("learned_adjustments", {}),
    }

    result = await db_service.update_user(user_id, {
        "energy_profile": updated_energy,
        "last_active_at": datetime.utcnow()
    })

    if not result:
        raise HTTPException(status_code=404, detail="Failed to update energy profile")

    return UserResponse(**result)


@router.get("/users/me/profile", response_model=UserProfileResponse)
async def get_user_profile(user_id: str = Depends(get_current_user)):
    """
    Get full user profile (personality + decision preferences)

    Returns both the UserProfile (personality traits learned from behavior)
    and UserDecisionProfile (decision-making preferences).

    Note: Uses the user_id field value for profile lookups.
    """
    # Get the user's user_id field value (not the database id)
    user = await db_service.get_user(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Use the user_id field for profile lookups
    user_field_id = user.get("user_id") or user_id

    # Get personality profile
    personality_profile = profile_service.get_or_create_profile(user_field_id)

    # Get decision profile
    decision_profile = decision_profile_service.get_or_create_profile(user_field_id)

    # Get profile summaries
    personality_summary = profile_service.get_profile_summary(user_field_id)
    decision_summary = decision_profile_service.get_profile_summary(user_field_id)

    return UserProfileResponse(
        user_id=user_field_id,
        relationships=personality_summary.get("relationships", {}),
        identity=personality_summary.get("identity", {}),
        preferences=personality_summary.get("preferences", {}),
        habits=personality_summary.get("habits", {}),
        total_points=personality_summary.get("total_points", 0),
        time_preference=decision_summary.get("time_preference", {}),
        meeting_preference=decision_summary.get("meeting_preference", {}),
        energy_profile=decision_summary.get("energy_profile", {}),
        conflict_resolution=decision_summary.get("conflict_resolution", {}),
        scenario_preferences=decision_summary.get("scenario_preferences", {}),
        explicit_rules=decision_summary.get("explicit_rules", []),
        updated_at=decision_profile.updated_at
    )


@router.get("/users/me/stats", response_model=UserStatsResponse)
async def get_user_stats(user_id: str = Depends(get_current_user)):
    """
    Get user statistics

    Returns aggregated statistics about events, profile data points,
    and user activity.
    """
    # Get user info
    user = await db_service.get_user(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Get all events for user
    all_events = await db_service.get_events(user_id, {}, limit=10000)

    # Calculate statistics
    total_events = len(all_events)
    pending_events = sum(1 for e in all_events if e.get("status") == "PENDING")
    completed_events = sum(1 for e in all_events if e.get("status") == "COMPLETED")
    cancelled_events = sum(1 for e in all_events if e.get("status") == "CANCELLED")

    # Category breakdown
    events_by_category = {}
    for event in all_events:
        category = event.get("category", "UNKNOWN")
        events_by_category[category] = events_by_category.get(category, 0) + 1

    # Type breakdown
    events_by_type = {}
    for event in all_events:
        event_type = event.get("event_type", "UNKNOWN")
        events_by_type[event_type] = events_by_type.get(event_type, 0) + 1

    # Get user_id field for profile lookups
    user_field_id = user.get("user_id") or user_id

    # Get profile stats
    personality_profile = profile_service.get_or_create_profile(user_field_id)
    decision_profile = decision_profile_service.get_or_create_profile(user_field_id)

    return UserStatsResponse(
        user_id=user_field_id,
        total_events=total_events,
        pending_events=pending_events,
        completed_events=completed_events,
        cancelled_events=cancelled_events,
        events_by_category=events_by_category,
        events_by_type=events_by_type,
        profile_points=personality_profile.total_points,
        decision_confidence=decision_profile.confidence_scores,
        last_active_at=user.get("last_active_at"),
        created_at=user.get("created_at")
    )

# Note: Register and login endpoints are handled by /api/v1/auth router
# These are kept here for potential future use but currently return 404

# ==================== Onboarding Status ====================

@router.get("/users/me/onboarding-status")
async def get_onboarding_status(user_id: str = Depends(get_current_user)):
    """
    获取用户的破冰状态

    返回 { "needs_onboarding": true/false }
    前端根据此字段决定是否显示"唤醒"按钮替代输入框。
    """
    user = await db_service.get_user(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    user_field_id = user.get("user_id") or user_id
    user_profile = profile_service.get_or_create_profile(user_field_id)

    return {
        "needs_onboarding": user_profile.preferences.get("needs_onboarding", True)
    }

@router.post("/users/me/onboarding-status/dismiss")
async def dismiss_onboarding_status(user_id: str = Depends(get_current_user)):
    """
    隐藏破冰"唤醒"按钮（由前端在点击按钮时触发）
    """
    user = await db_service.get_user(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    user_field_id = user.get("user_id") or user_id
    user_profile = profile_service.get_or_create_profile(user_field_id)
    
    # Update preference
    user_profile.preferences["needs_onboarding"] = False
    profile_service.save_profile(user_field_id, user_profile)
    
    return {"status": "success", "needs_onboarding": False}

# ==================== Notification Settings ====================

@router.get("/users/me/notification-settings", response_model=NotificationSettings)
async def get_notification_settings(user_id: str = Depends(get_current_user)):
    """
    获取用户通知设置

    返回用户的作息时间和通知偏好配置。
    """
    # 获取用户信息
    user = await db_service.get_user(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # 使用 user_id 字段查找 profile
    user_field_id = user.get("user_id") or user_id

    # 获取 UserProfile
    user_profile = profile_service.get_or_create_profile(user_field_id)

    # 从 preferences 中提取通知设置
    return NotificationSettings.from_preferences(user_profile.preferences)


@router.put("/users/me/notification-settings", response_model=NotificationSettings)
async def update_notification_settings(
    settings: NotificationSettings,
    user_id: str = Depends(get_current_user)
):
    """
    更新用户通知设置
    
    更新作息时间和通知偏好配置。
    
    **示例请求:**
    ```json
    {
        "wake_time": "07:30",
        "sleep_time": "23:00",
        "morning_briefing_enabled": true,
        "afternoon_checkin_enabled": true,
        "evening_switch_enabled": true,
        "closing_ritual_enabled": true,
        "event_reminders_enabled": true,
        "event_reminder_minutes": 30
    }
    ```
    """
    # 获取用户信息
    user = await db_service.get_user(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # 使用 user_id 字段查找 profile
    user_field_id = user.get("user_id") or user_id

    # 获取现有 UserProfile
    user_profile = profile_service.get_or_create_profile(user_field_id)

    # 合并新的通知设置到 preferences
    new_preferences = settings.to_preferences_dict()
    for key, value in new_preferences.items():
        user_profile.update_preference(key, value)

    # 保存更新后的 profile
    profile_service.save_profile(user_field_id, user_profile)

    return settings


@router.post("/users/register", include_in_schema=False)
async def register_user():
    """Register a new user - use /api/v1/auth/register instead"""
    raise HTTPException(status_code=404, detail="Use /api/v1/auth/register instead")


@router.post("/users/login", include_in_schema=False)
async def login_user():
    """User login - use /api/v1/auth/login instead"""
    raise HTTPException(status_code=404, detail="Use /api/v1/auth/login instead")
