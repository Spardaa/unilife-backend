"""
Snapshots API - Schedule snapshot management
"""
from typing import List
from fastapi import APIRouter, HTTPException

from app.schemas.snapshots import SnapshotResponse, SnapshotRevertResponse

router = APIRouter()


@router.get("/snapshots", response_model=List[SnapshotResponse])
async def get_snapshots():
    """Get all snapshots for the user"""
    raise HTTPException(status_code=501, detail="Not implemented yet")


@router.post("/snapshots/{snapshot_id}/revert", response_model=SnapshotRevertResponse)
async def revert_snapshot(snapshot_id: str):
    """Revert to a specific snapshot"""
    raise HTTPException(status_code=501, detail="Not implemented yet")
