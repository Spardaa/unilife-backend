"""
Projects API - CRUD operations for Life Projects
"""
from typing import List, Optional
from datetime import datetime
from fastapi import APIRouter, HTTPException, Query, Depends
from pydantic import BaseModel, Field

from app.services.db import db_service
from app.middleware.auth import get_current_user

router = APIRouter()


# MARK: - Request/Response Schemas

class ProjectCreate(BaseModel):
    """Schema for creating a project"""
    title: str
    description: Optional[str] = None
    type: str = "FINITE"  # FINITE or INFINITE
    base_tier: int = 1    # 0=Core, 1=Growth, 2=Interest
    energy_type: str = "BALANCED"  # MENTAL, PHYSICAL, BALANCED
    target_kpi: Optional[dict] = None


class ProjectUpdate(BaseModel):
    """Schema for updating a project"""
    title: Optional[str] = None
    description: Optional[str] = None
    type: Optional[str] = None
    base_tier: Optional[int] = None
    current_mode: Optional[str] = None
    energy_type: Optional[str] = None
    target_kpi: Optional[dict] = None
    is_active: Optional[bool] = None


class SetModeRequest(BaseModel):
    """Schema for setting project mode"""
    mode: str = Field(..., description="NORMAL or SPRINT")


class SetModeResponse(BaseModel):
    """Response for set mode operation"""
    success: bool
    project: Optional[dict] = None
    warning: bool = False
    existing_sprint: Optional[str] = None
    message: Optional[str] = None


# MARK: - Routes

@router.get("")
async def get_projects(
    user_id: str = Depends(get_current_user),
    active_only: bool = Query(True, description="Filter to active projects only"),
    include_stats: bool = Query(False, description="Include task statistics")
):
    """
    Get all projects for the authenticated user.
    
    Returns a list of projects with optional statistics.
    """
    try:
        # Map active_only to is_active (None means get all)
        is_active = True if active_only else None
        projects = await db_service.get_projects(
            user_id=user_id,
            is_active=is_active,
            include_stats=include_stats
        )
        return projects
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{project_id}")
async def get_project(
    project_id: str,
    user_id: str = Depends(get_current_user)
):
    """
    Get a specific project by ID.
    """
    try:
        project = await db_service.get_project(project_id, user_id)
        if not project:
            raise HTTPException(status_code=404, detail="Project not found")
        return project
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("")
async def create_project(
    project: ProjectCreate,
    user_id: str = Depends(get_current_user)
):
    """
    Create a new project.
    """
    try:
        project_data = {
            "user_id": user_id,
            "title": project.title,
            "description": project.description,
            "type": project.type,
            "base_tier": project.base_tier,
            "energy_type": project.energy_type,
            "target_kpi": project.target_kpi,
        }
        created = await db_service.create_project(project_data)
        return created
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/{project_id}")
async def update_project(
    project_id: str,
    project: ProjectUpdate,
    user_id: str = Depends(get_current_user)
):
    """
    Update an existing project.
    """
    try:
        # Filter out None values
        update_data = {k: v for k, v in project.model_dump().items() if v is not None}
        
        updated = await db_service.update_project(project_id, user_id, update_data)
        if not updated:
            raise HTTPException(status_code=404, detail="Project not found")
        return updated
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{project_id}/mode")
async def set_project_mode(
    project_id: str,
    request: SetModeRequest,
    user_id: str = Depends(get_current_user)
):
    """
    Set the project mode (NORMAL or SPRINT).
    
    Returns a warning if another project is already in SPRINT mode.
    """
    try:
        result = await db_service.set_project_mode(project_id, user_id, request.mode)
        return SetModeResponse(**result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{project_id}")
async def delete_project(
    project_id: str,
    user_id: str = Depends(get_current_user)
):
    """
    Delete (soft archive) a project.
    """
    try:
        success = await db_service.delete_project(project_id, user_id)
        if not success:
            raise HTTPException(status_code=404, detail="Project not found")
        return {"success": True, "message": "Project archived"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/quests/overview")
async def get_quest_overview(
    user_id: str = Depends(get_current_user),
    date: Optional[str] = Query(None, description="Date in YYYY-MM-DD format")
):
    """
    Get quest overview (tasks grouped by MAIN/SIDE/DAILY).
    """
    try:
        target_date = None
        if date:
            target_date = datetime.strptime(date, "%Y-%m-%d")
        else:
            target_date = datetime.now()
        
        overview = await db_service.get_quest_overview(user_id, target_date)
        return overview
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
