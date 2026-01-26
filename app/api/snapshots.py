"""
Snapshots API - Schedule snapshot management
"""
from typing import List, Optional
from fastapi import APIRouter, HTTPException, Query, Depends

from app.schemas.snapshots import SnapshotResponse, SnapshotRevertResponse
from app.services.db import db_service
from app.services.snapshot import snapshot_manager
from app.middleware.auth import get_current_user

router = APIRouter()


@router.get("/snapshots", response_model=List[SnapshotResponse])
async def get_snapshots(
    user_id: str = Depends(get_current_user),
    limit: int = Query(10, ge=1, le=100, description="Maximum number of snapshots to return"),
    include_reverted: bool = Query(False, description="Include reverted snapshots")
):
    """
    Get all snapshots for the user

    Returns the most recent snapshots, ordered by creation time (newest first).
    """
    snapshots = await snapshot_manager.get_snapshot_history(user_id, limit=limit)

    # Filter out reverted snapshots if requested
    if not include_reverted:
        snapshots = [s for s in snapshots if not s.get("is_reverted", False)]

    return [SnapshotResponse(**snapshot) for snapshot in snapshots]


@router.post("/snapshots/{snapshot_id}/revert", response_model=SnapshotRevertResponse)
async def revert_snapshot(
    snapshot_id: str,
    user_id: str = Depends(get_current_user)
):
    """
    Revert to a specific snapshot

    This will undo all changes that were made in this snapshot:
    - Created events will be deleted
    - Updated events will be restored to their previous state
    - Deleted events will be recreated

    Returns details of what was reverted.
    """
    # First verify the snapshot belongs to this user
    snapshot = await db_service.get_snapshot(snapshot_id, user_id)
    if not snapshot:
        raise HTTPException(status_code=404, detail="Snapshot not found")

    # Check if already reverted
    if snapshot.get("is_reverted"):
        raise HTTPException(status_code=400, detail="This snapshot has already been reverted")

    # Perform the revert
    result = await snapshot_manager.revert_snapshot(snapshot_id, user_id)

    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("message", "Failed to revert snapshot"))

    return SnapshotRevertResponse(
        snapshot_id=snapshot_id,
        message=result.get("message", "Snapshot reverted successfully"),
        reverted_events=result.get("reverted_events", []),
        reverted_at=result.get("reverted_at")
    )


@router.post("/snapshots/undo", response_model=SnapshotRevertResponse)
async def undo_last_change(user_id: str = Depends(get_current_user)):
    """
    Undo the most recent change (convenience endpoint)

    This is a shortcut for reverting the most recent non-reverted snapshot.
    """
    result = await snapshot_manager.undo_last_change(user_id)

    if not result.get("success"):
        raise HTTPException(
            status_code=400,
            detail=result.get("message", "No changes to undo")
        )

    snapshot_id = result.get("snapshot_id")
    return SnapshotRevertResponse(
        snapshot_id=snapshot_id,
        message=result.get("message", "Last change undone"),
        reverted_events=result.get("reverted_events", []),
        reverted_at=result.get("reverted_at")
    )
