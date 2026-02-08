"""
Devices API - Device registration and management for push notifications
"""
from typing import List, Optional
from datetime import datetime
from fastapi import APIRouter, HTTPException, Query, Depends

from app.schemas.devices import (
    DeviceRegisterRequest, DeviceUpdateRequest, DeviceResponse, DeviceListResponse
)
from app.models.device import Device
from app.middleware.auth import get_current_user
from sqlalchemy import create_engine, text
from sqlalchemy.pool import StaticPool
from sqlalchemy.orm import sessionmaker, Session
from app.config import settings

router = APIRouter()


class DeviceService:
    """Service for device management"""

    def __init__(self):
        db_path = settings.database_url.replace("sqlite:///", "")
        self.engine = create_engine(
            f"sqlite:///{db_path}",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
            echo=False
        )
        self.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=self.engine)
        self._ensure_table_exists()

    def get_session(self) -> Session:
        return self.SessionLocal()

    def _ensure_table_exists(self):
        """Ensure devices table exists"""
        db = self.get_session()
        try:
            db.execute(text("""
                CREATE TABLE IF NOT EXISTS devices (
                    id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    platform TEXT NOT NULL,
                    token TEXT NOT NULL,
                    device_id TEXT,
                    device_name TEXT,
                    device_model TEXT,
                    os_version TEXT,
                    app_version TEXT,
                    metadata TEXT,
                    is_active BOOLEAN DEFAULT 1,
                    last_used_at TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
            """))
            db.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_devices_user_id ON devices(user_id)
            """))
            db.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_devices_device_id ON devices(device_id)
            """))
            db.commit()
        except Exception as e:
            db.rollback()
            print(f"Error ensuring devices table exists: {e}")
        finally:
            db.close()

    async def register_device(self, user_id: str, request: DeviceRegisterRequest) -> Device:
        """Register or update a device"""
        import json

        db = self.get_session()
        try:
            now = datetime.utcnow()

            # Check if device already exists (by user_id + device_id or user_id + token)
            existing = None
            if request.device_id:
                existing = db.execute(
                    text("""SELECT * FROM devices WHERE user_id = :user_id AND device_id = :device_id"""),
                    {"user_id": user_id, "device_id": request.device_id}
                ).fetchone()

            if not existing:
                existing = db.execute(
                    text("""SELECT * FROM devices WHERE user_id = :user_id AND token = :token"""),
                    {"user_id": user_id, "token": request.token}
                ).fetchone()

            metadata_json = json.dumps(request.metadata) if request.metadata else None

            if existing:
                # Update existing device
                db.execute(
                    text("""UPDATE devices SET
                        platform = :platform,
                        token = :token,
                        device_name = :device_name,
                        device_model = :device_model,
                        os_version = :os_version,
                        app_version = :app_version,
                        metadata = :metadata,
                        is_active = 1,
                        last_used_at = :last_used_at,
                        updated_at = :updated_at
                        WHERE id = :id"""),
                    {
                        "platform": request.platform,
                        "token": request.token,
                        "device_name": request.device_name,
                        "device_model": request.device_model,
                        "os_version": request.os_version,
                        "app_version": request.app_version,
                        "metadata": metadata_json,
                        "last_used_at": now.isoformat(),
                        "updated_at": now.isoformat(),
                        "id": existing[0]
                    }
                )
                db.commit()
                device_id = existing[0]
            else:
                # Create new device
                import uuid
                new_id = str(uuid.uuid4())
                db.execute(
                    text("""INSERT INTO devices
                        (id, user_id, platform, token, device_id, device_name, device_model,
                         os_version, app_version, metadata, is_active, last_used_at, created_at, updated_at)
                        VALUES (:id, :user_id, :platform, :token, :device_id, :device_name, :device_model,
                                :os_version, :app_version, :metadata, 1, :last_used_at, :created_at, :updated_at)"""),
                    {
                        "id": new_id,
                        "user_id": user_id,
                        "platform": request.platform,
                        "token": request.token,
                        "device_id": request.device_id,
                        "device_name": request.device_name,
                        "device_model": request.device_model,
                        "os_version": request.os_version,
                        "app_version": request.app_version,
                        "metadata": metadata_json,
                        "last_used_at": now.isoformat(),
                        "created_at": now.isoformat(),
                        "updated_at": now.isoformat()
                    }
                )
                db.commit()
                device_id = new_id

            # Return the device
            result = db.execute(
                text("""SELECT * FROM devices WHERE id = :id"""),
                {"id": device_id}
            ).fetchone()

            return self._row_to_device(result)

        except Exception as e:
            db.rollback()
            raise e
        finally:
            db.close()

    async def get_user_devices(self, user_id: str) -> List[Device]:
        """Get all devices for a user"""
        db = self.get_session()
        try:
            results = db.execute(
                text("""SELECT * FROM devices WHERE user_id = :user_id ORDER BY created_at DESC"""),
                {"user_id": user_id}
            ).fetchall()
            return [self._row_to_device(row) for row in results]
        except Exception as e:
            return []
        finally:
            db.close()

    async def get_device(self, device_id: str, user_id: str) -> Optional[Device]:
        """Get a specific device"""
        db = self.get_session()
        try:
            result = db.execute(
                text("""SELECT * FROM devices WHERE id = :id AND user_id = :user_id"""),
                {"id": device_id, "user_id": user_id}
            ).fetchone()
            if result:
                return self._row_to_device(result)
            return None
        finally:
            db.close()

    async def update_device(self, device_id: str, user_id: str, update_data: dict) -> Optional[Device]:
        """Update device information"""
        db = self.get_session()
        try:
            # Build update query dynamically
            update_fields = []
            params = {"id": device_id, "user_id": user_id, "updated_at": datetime.utcnow().isoformat()}

            if "device_name" in update_data:
                update_fields.append("device_name = :device_name")
                params["device_name"] = update_data["device_name"]
            if "is_active" in update_data:
                update_fields.append("is_active = :is_active")
                params["is_active"] = 1 if update_data["is_active"] else 0
            if "metadata" in update_data:
                update_fields.append("metadata = :metadata")
                params["metadata"] = update_data["metadata"]

            if update_fields:
                query = f"""UPDATE devices SET {', '.join(update_fields)}, updated_at = :updated_at
                          WHERE id = :id AND user_id = :user_id"""
                db.execute(text(query), params)
                db.commit()

                result = db.execute(
                    text("""SELECT * FROM devices WHERE id = :id"""),
                    {"id": device_id}
                ).fetchone()
                if result:
                    return self._row_to_device(result)
            return None
        except Exception as e:
            db.rollback()
            raise e
        finally:
            db.close()

    async def delete_device(self, device_id: str, user_id: str) -> bool:
        """Delete a device"""
        db = self.get_session()
        try:
            db.execute(
                text("""DELETE FROM devices WHERE id = :id AND user_id = :user_id"""),
                {"id": device_id, "user_id": user_id}
            )
            db.commit()
            return True
        except Exception as e:
            db.rollback()
            return False
        finally:
            db.close()

    def _row_to_device(self, row) -> Device:
        """Convert database row to Device model"""
        import json
        return Device(
            id=row[0],
            user_id=row[1],
            platform=row[2],
            token=row[3],
            device_id=row[4],
            device_name=row[5],
            device_model=row[6],
            os_version=row[7],
            app_version=row[8],
            metadata=json.loads(row[9]) if row[9] else {},
            is_active=bool(row[10]),
            last_used_at=datetime.fromisoformat(row[11]) if row[11] else None,
            created_at=datetime.fromisoformat(row[12]),
            updated_at=datetime.fromisoformat(row[13])
        )


# Global device service instance
device_service = DeviceService()


@router.post("/devices/register", response_model=DeviceResponse, status_code=201)
async def register_device(
    request: DeviceRegisterRequest,
    user_id: str = Depends(get_current_user)
):
    """
    Register a device for push notifications

    If a device with the same device_id or token already exists,
    it will be updated instead of creating a duplicate.
    """
    print(f"[Device] Registering device token={request.token[:20]}... for user_id={user_id}")
    device = await device_service.register_device(user_id, request)
    return DeviceResponse(**device.to_dict())


# Alias for POST /devices (same as /devices/register)
@router.post("/devices", response_model=DeviceResponse, status_code=201)
async def register_device_alt(
    request: DeviceRegisterRequest,
    user_id: str = Depends(get_current_user)
):
    """
    Register a device for push notifications (alias for /devices/register)
    """
    device = await device_service.register_device(user_id, request)
    return DeviceResponse(**device.to_dict())


@router.get("/devices", response_model=DeviceListResponse)
async def get_devices(user_id: str = Depends(get_current_user)):
    """
    Get all devices for the current user

    Returns a list of all registered devices with their status.
    """
    devices = await device_service.get_user_devices(user_id)
    return DeviceListResponse(
        devices=[DeviceResponse(**d.to_dict()) for d in devices],
        total=len(devices)
    )


@router.get("/devices/{device_id}", response_model=DeviceResponse)
async def get_device(
    device_id: str,
    user_id: str = Depends(get_current_user)
):
    """Get a specific device by ID"""
    device = await device_service.get_device(device_id, user_id)
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")
    return DeviceResponse(**device.to_dict())


@router.put("/devices/{device_id}", response_model=DeviceResponse)
async def update_device(
    device_id: str,
    request: DeviceUpdateRequest,
    user_id: str = Depends(get_current_user)
):
    """Update device information"""
    update_data = request.model_dump(exclude_unset=True)
    if not update_data:
        raise HTTPException(status_code=400, detail="No fields to update")

    device = await device_service.update_device(device_id, user_id, update_data)
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")
    return DeviceResponse(**device.to_dict())


@router.delete("/devices/{device_id}", status_code=204)
async def delete_device(
    device_id: str,
    user_id: str = Depends(get_current_user)
):
    """
    Delete a device

    Removes the device registration and stops push notifications to it.
    """
    success = await device_service.delete_device(device_id, user_id)
    if not success:
        raise HTTPException(status_code=404, detail="Device not found")
