"""
Notification Service - Push notification management

Supports sending push notifications to multiple platforms (iOS/APNs, Android/FCM, Web).
Designed to work with the Device registry for token management.
"""
import httpx
import json
import time as _time
import asyncio
from typing import List, Optional, Dict, Any
from datetime import datetime
from sqlalchemy import create_engine, Column, String, DateTime, Integer, Text, JSON
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.ext.declarative import declarative_base

from app.config import settings
from app.models.notification import (
    NotificationPlatform,
    NotificationType,
    NotificationStatus,
    NotificationPriority,
    NotificationRecord,
    NotificationPayload,
    NotificationTemplate,
    BUILTIN_TEMPLATES
)
from app.models.device import DeviceDB

# Create base for notification models
Base = declarative_base()


class NotificationRecordDB(Base):
    """Database model for notification records"""
    __tablename__ = "notifications"

    id = Column(String, primary_key=True)
    user_id = Column(String, index=True, nullable=False)
    device_id = Column(String, nullable=True, index=True)  # None means all devices
    platform = Column(String, nullable=False)

    # Notification content
    type = Column(String, nullable=False)
    priority = Column(String, nullable=False)
    payload = Column(JSON, nullable=False)

    # Delivery tracking
    status = Column(String, nullable=False, default=NotificationStatus.PENDING.value)
    scheduled_for = Column(DateTime, nullable=True)
    sent_at = Column(DateTime, nullable=True)
    delivered_at = Column(DateTime, nullable=True)
    error_message = Column(Text, nullable=True)

    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow)
    retry_count = Column(Integer, default=0)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "user_id": self.user_id,
            "device_id": self.device_id,
            "platform": self.platform,
            "type": self.type,
            "priority": self.priority,
            "payload": self.payload,
            "status": self.status,
            "scheduled_for": self.scheduled_for.isoformat() if self.scheduled_for else None,
            "sent_at": self.sent_at.isoformat() if self.sent_at else None,
            "delivered_at": self.delivered_at.isoformat() if self.delivered_at else None,
            "error_message": self.error_message,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "retry_count": self.retry_count
        }


class NotificationService:
    """
    Push notification service

    Handles sending notifications to multiple platforms.
    For production use with APNs, you'll need to configure Apple Developer credentials.
    """

    def __init__(self):
        self.engine = None
        self.SessionLocal = None
        self._initialized = False

        # APNs configuration (these would come from environment/config in production)
        self.apns_key_id = getattr(settings, 'APNS_KEY_ID', None)
        self.apns_team_id = getattr(settings, 'APNS_TEAM_ID', None)
        self.apns_bundle_id = getattr(settings, 'APNS_BUNDLE_ID', None)
        self.apns_use_sandbox = getattr(settings, 'APNS_USE_SANDBOX', True)

        # APNs JWT 缓存 (避免每次推送都读文件 + 签名)
        self._apns_key_secret: Optional[str] = None   # .p8 文件内容缓存
        self._apns_jwt_token: Optional[str] = None     # 当前有效的 JWT
        self._apns_jwt_issued_at: float = 0            # JWT 签发时间戳
        self._apns_jwt_ttl: int = 45 * 60              # JWT 缓存 45 分钟

        # httpx HTTP/2 客户端 (长连接复用)
        self._http_client: Optional[httpx.AsyncClient] = None

        # Templates
        self.templates: Dict[str, NotificationTemplate] = BUILTIN_TEMPLATES.copy()

    def initialize(self):
        """Initialize notification service and database tables"""
        if not self._initialized:
            self.engine = create_engine(
                settings.database_url,
                connect_args={"check_same_thread": False}
            )

            self.SessionLocal = sessionmaker(
                autocommit=False,
                autoflush=False,
                bind=self.engine
            )

            # Create notifications table
            Base.metadata.create_all(bind=self.engine)

            self._initialized = True
            print("Notification service initialized")

    def _ensure_initialized(self):
        """Ensure service is initialized"""
        if not self._initialized:
            self.initialize()

    def get_session(self) -> Session:
        """Get database session"""
        self._ensure_initialized()
        return self.SessionLocal()

    # ==================== Template Management ====================

    def get_template(self, name: str) -> Optional[NotificationTemplate]:
        """Get a notification template by name"""
        return self.templates.get(name)

    def register_template(self, template: NotificationTemplate):
        """Register a custom notification template"""
        self.templates[template.name] = template

    # ==================== Sending Notifications ====================

    async def send_notification(
        self,
        user_id: str,
        payload: NotificationPayload,
        notification_type: NotificationType,
        device_id: Optional[str] = None,
        platform: Optional[NotificationPlatform] = None,
        priority: NotificationPriority = NotificationPriority.NORMAL,
        scheduled_for: Optional[datetime] = None
    ) -> NotificationRecord:
        """
        Send a push notification

        Args:
            user_id: User to receive notification
            payload: Notification payload (title, body, etc.)
            notification_type: Type of notification
            device_id: Target device (None for all user devices)
            platform: Target platform (None for all platforms)
            priority: Notification priority
            scheduled_for: Schedule for future (None=immediate)

        Returns:
            NotificationRecord with delivery status
        """
        self._ensure_initialized()

        # Get user's devices
        with self.get_session() as session:
            if device_id:
                devices = [session.query(DeviceDB).filter(
                    DeviceDB.id == device_id,
                    DeviceDB.user_id == user_id,
                    DeviceDB.active == True
                ).first()]
            else:
                # Get all active devices for user, filtered by platform if specified
                query = session.query(DeviceDB).filter(
                    DeviceDB.user_id == user_id,
                    DeviceDB.is_active == True
                )
                if platform:
                    query = query.filter(DeviceDB.platform == platform.value)
                devices = query.all()
                print(f"[Notification] Found {len(devices)} active devices for user {user_id}")

            if not devices:
                # No devices found, create a failed record
                record = NotificationRecord(
                    user_id=user_id,
                    device_id=device_id,
                    platform=platform.value if platform else NotificationPlatform.UNKNOWN.value,
                    type=notification_type,
                    priority=priority,
                    payload=payload,
                    status=NotificationStatus.FAILED,
                    error_message="No active devices found",
                    scheduled_for=scheduled_for
                )
                return self._save_record(record)

            # Send to each device
            results = []
            for device in devices:
                device_platform = self._map_device_to_notification_platform(device.platform)
                record = NotificationRecord(
                    user_id=user_id,
                    device_id=device.id,
                    platform=device_platform,
                    type=notification_type,
                    priority=priority,
                    payload=payload,
                    scheduled_for=scheduled_for
                )

                if scheduled_for and scheduled_for > datetime.utcnow():
                    # Scheduled for later, save as pending
                    results.append(self._save_record(record))
                else:
                    # Send immediately
                    result = await self._send_to_device(record, device)
                    results.append(result)

            return results[0] if len(results) == 1 else results[0]

    async def send_template(
        self,
        template_name: str,
        user_id: str,
        **variables
    ) -> NotificationRecord:
        """
        Send a notification using a template

        Args:
            template_name: Name of the template to use
            user_id: User to receive notification
            **variables: Template variables

        Returns:
            NotificationRecord with delivery status
        """
        template = self.get_template(template_name)
        if not template:
            raise ValueError(f"Template not found: {template_name}")

        payload = template.render(**variables)
        return await self.send_notification(
            user_id=user_id,
            payload=payload,
            notification_type=template.type,
            priority=template.default_priority
        )

    def _map_device_to_notification_platform(self, device_platform: str) -> NotificationPlatform:
        """Map device platform string to NotificationPlatform enum"""
        platform_map = {
            "ios": NotificationPlatform.APNS,
            "android": NotificationPlatform.FCM,
            "web": NotificationPlatform.WEB
        }
        return platform_map.get(device_platform, NotificationPlatform.APNS)

    async def _send_to_device(
        self,
        record: NotificationRecord,
        device: DeviceDB
    ) -> NotificationRecord:
        """Send notification to a specific device based on platform"""
        try:
            # Map device platform to notification platform
            notification_platform = self._map_device_to_notification_platform(device.platform)

            if notification_platform == NotificationPlatform.APNS:
                return await self._send_apns(record, device)
            elif notification_platform == NotificationPlatform.FCM:
                return await self._send_fcm(record, device)
            elif notification_platform == NotificationPlatform.WEB:
                return await self._send_web_push(record, device)
            else:
                record.status = NotificationStatus.FAILED
                record.error_message = f"Unsupported platform: {device.platform}"
                return self._save_record(record)

        except Exception as e:
            record.status = NotificationStatus.FAILED
            record.error_message = str(e)
            return self._save_record(record)

    def _get_apns_token(self) -> str:
        """
        获取有效的 APNs JWT Token（带缓存）
        
        JWT 有效期缓存 45 分钟（Apple 允许最长 60 分钟），
        仅在过期时才重新读取 .p8 密钥文件并重新签名。
        """
        from pathlib import Path
        from jose import jwt
        
        now = _time.time()
        
        # 如果缓存的 Token 仍然有效，直接返回
        if self._apns_jwt_token and (now - self._apns_jwt_issued_at) < self._apns_jwt_ttl:
            return self._apns_jwt_token
        
        # 首次调用或缓存过期：读取密钥文件（也做缓存）
        if not self._apns_key_secret:
            key_path = Path(settings.apns_key_path)
            if not key_path.exists():
                root_path = Path.cwd()
                potential_path = root_path / settings.apns_key_path
                if potential_path.exists():
                    key_path = potential_path
                else:
                    parts = list(Path(settings.apns_key_path).parts)
                    if parts and parts[0] == "unilife-backend":
                        potential_path = root_path / Path(*parts[1:])
                        if potential_path.exists():
                            key_path = potential_path
            
            if not key_path.exists():
                raise FileNotFoundError(f"APNs key file not found at {settings.apns_key_path}")
            
            with open(key_path, "r") as f:
                self._apns_key_secret = f.read()
            print(f"[APNs] Loaded .p8 key file from {key_path}")
        
        # 签发新 JWT
        algorithm = "ES256"
        headers = {"alg": algorithm, "kid": settings.apns_key_id}
        payload_jwt = {"iss": settings.apns_team_id, "iat": int(now)}
        
        self._apns_jwt_token = jwt.encode(
            payload_jwt, self._apns_key_secret,
            algorithm=algorithm, headers=headers
        )
        self._apns_jwt_issued_at = now
        print(f"[APNs] JWT token refreshed (valid for {self._apns_jwt_ttl // 60} min)")
        
        return self._apns_jwt_token

    async def _get_http_client(self) -> httpx.AsyncClient:
        """获取共享的 HTTP/2 异步客户端（长连接复用）"""
        if self._http_client is None or self._http_client.is_closed:
            self._http_client = httpx.AsyncClient(
                http2=True,
                timeout=httpx.Timeout(30.0, connect=10.0),
                limits=httpx.Limits(
                    max_keepalive_connections=20,
                    max_connections=50
                )
            )
        return self._http_client

    async def _send_apns(
        self,
        record: NotificationRecord,
        device: DeviceDB
    ) -> NotificationRecord:
        """
        Send notification via Apple Push Notification Service (APNs)
        
        使用 httpx HTTP/2 长连接 + JWT 缓存，替代原来的 curl 子进程方案。
        """
        try:
            # Check if APNs is configured
            if not all([settings.apns_key_id, settings.apns_team_id, settings.apns_key_path, settings.apns_bundle_id]):
                print("[APNs] Configuration missing, falling back to mock send.")
                return await self._send_apns_mock(record, device)

            # 获取缓存的 JWT Token（过期时自动刷新）
            try:
                token = self._get_apns_token()
            except FileNotFoundError as e:
                record.status = NotificationStatus.FAILED
                record.error_message = str(e)
                print(f"[APNs] {e}")
                return self._save_record(record)

            # Determine endpoint
            endpoint = "https://api.development.push.apple.com" if settings.apns_use_sandbox else "https://api.push.apple.com"
            url = f"{endpoint}/3/device/{device.token}"

            # Prepare payload
            aps = {
                "alert": {
                    "title": record.payload.title,
                    "body": record.payload.body,
                },
                "sound": record.payload.sound or "default",
                "badge": record.payload.badge or 1
            }
            
            # Add platform-specific fields
            if record.payload.category:
                aps["category"] = record.payload.category
            
            # Add custom data
            full_payload = {"aps": aps}
            if record.payload.data:
                full_payload.update(record.payload.data)

            print(f"[APNs] Sending to {device.token[:8]}... via httpx")
            
            # 使用 httpx HTTP/2 异步请求（长连接复用，无子进程开销）
            client = await self._get_http_client()
            headers = {
                "apns-topic": settings.apns_bundle_id,
                "apns-push-type": "alert",
                "content-type": "application/json",
                "authorization": f"bearer {token}"
            }
            
            response = await client.post(url, json=full_payload, headers=headers)
            status_code = response.status_code
            
            if status_code == 200:
                record.status = NotificationStatus.SENT
                record.sent_at = datetime.utcnow()
                print(f"[APNs] Sent successfully. Status: 200. Token: {device.token[:10]}...")
            else:
                response_body = response.text
                record.status = NotificationStatus.FAILED
                record.error_message = f"APNs Error {status_code}: {response_body}"
                print(f"[APNs] Failed. Status: {status_code}. Body: {response_body}")
                
                # 410 = token 永久失效（App 已卸载或 token 已更新）
                # Apple 官方要求收到 410 后停止向该 token 发送推送
                if status_code == 410:
                    try:
                        with self.get_session() as session:
                            db_device = session.query(DeviceDB).filter(DeviceDB.id == device.id).first()
                            if db_device:
                                db_device.is_active = False
                                session.commit()
                                print(f"[APNs] Deactivated expired device {device.token[:10]}...")
                    except Exception as deactivate_err:
                        print(f"[APNs] Failed to deactivate device: {deactivate_err}")
                
                # 403 = JWT 被拒绝，可能是 token 过期了，清除缓存让下次刷新
                if status_code == 403:
                    self._apns_jwt_token = None
                    self._apns_jwt_issued_at = 0
                    print(f"[APNs] JWT rejected, cache cleared for next retry")

            return self._save_record(record)

        except Exception as e:
            import traceback
            traceback.print_exc()
            record.status = NotificationStatus.FAILED
            record.error_message = f"Internal Error: {str(e)}"
            return self._save_record(record)

    async def _send_apns_mock(
        self,
        record: NotificationRecord,
        device: DeviceDB
    ) -> NotificationRecord:
        """
        Send notification via Apple Push Notification Service (APNs)

        Note: This is a simplified implementation for development.
        Production requires APNs certificate/token authentication.
        """
        # In development mode, we'll simulate the send
        # In production, use httpx to call APNs API with JWT auth

        # For now, mark as sent (development mode)
        record.status = NotificationStatus.SENT
        record.sent_at = datetime.utcnow()

        # Simulate APNs response
        # In production, you would:
        # 1. Generate JWT using your APNs key
        # 2. POST to https://api.development.push.apple.com/3/device/{device_token}
        # 3. Handle APNs response (200=success, 400=error, etc.)

        return self._save_record(record)

    async def _send_fcm(
        self,
        record: NotificationRecord,
        device: DeviceDB
    ) -> NotificationRecord:
        """
        Send notification via Firebase Cloud Messaging (FCM)

        Note: Not implemented in this version.
        """
        record.status = NotificationStatus.FAILED
        record.error_message = "FCM not yet implemented"
        return self._save_record(record)

    async def _send_web_push(
        self,
        record: NotificationRecord,
        device: DeviceDB
    ) -> NotificationRecord:
        """
        Send notification via Web Push API

        Note: Not implemented in this version.
        """
        record.status = NotificationStatus.FAILED
        record.error_message = "Web Push not yet implemented"
        return self._save_record(record)

    # ==================== Database Operations ====================

    def _save_record(self, record: NotificationRecord) -> NotificationRecord:
        """Save notification record to database"""
        with self.get_session() as session:
            db_record = NotificationRecordDB(
                id=record.id,
                user_id=record.user_id,
                device_id=record.device_id,
                platform=record.platform.value if isinstance(record.platform, NotificationPlatform) else record.platform,
                type=record.type.value if isinstance(record.type, NotificationType) else record.type,
                priority=record.priority.value if isinstance(record.priority, NotificationPriority) else record.priority,
                payload=record.payload.model_dump(),
                status=record.status.value if isinstance(record.status, NotificationStatus) else record.status,
                scheduled_for=record.scheduled_for,
                sent_at=record.sent_at,
                delivered_at=record.delivered_at,
                error_message=record.error_message,
                created_at=record.created_at,
                retry_count=record.retry_count
            )

            session.merge(db_record)
            session.commit()
            
            # Re-query to ensure we have latest state
            refreshed = session.query(NotificationRecordDB).get(record.id)
            return NotificationRecord(**refreshed.to_dict()) if refreshed else record

    async def process_pending_notifications(self):
        """Process pending notifications scheduled for now or past (CAS防重)"""
        self._ensure_initialized()
        
        # 1. 原子性地将 PENDING → PROCESSING，防止多 Worker 重复拿取
        claimed_ids = []
        with self.get_session() as session:
            now = datetime.utcnow()
            # 先查询符合条件的记录 ID
            rows = session.query(NotificationRecordDB.id).filter(
                NotificationRecordDB.status == NotificationStatus.PENDING.value,
                NotificationRecordDB.scheduled_for <= now
            ).all()
            candidate_ids = [r[0] for r in rows]
            
            if not candidate_ids:
                return
            
            # 原子更新: 仅更新仍然是 PENDING 的记录为 PROCESSING
            updated = session.query(NotificationRecordDB).filter(
                NotificationRecordDB.id.in_(candidate_ids),
                NotificationRecordDB.status == NotificationStatus.PENDING.value
            ).update(
                {"status": "processing"},
                synchronize_session="fetch"
            )
            session.commit()
            
            if updated == 0:
                return
            
            # 重新拉取被本 Worker 成功锁定的记录
            claimed_rows = session.query(NotificationRecordDB).filter(
                NotificationRecordDB.id.in_(candidate_ids),
                NotificationRecordDB.status == "processing"
            ).all()
            claimed_ids = [r.id for r in claimed_rows]
            pending_records = [NotificationRecord(**r.to_dict()) for r in claimed_rows]
            
        if not pending_records:
            return
            
        print(f"[Notification] Processing {len(pending_records)} pending notifications (CAS claimed)")
        
        # 2. 批量获取所有相关设备，避免 N+1 查询
        device_ids = list(set(r.device_id for r in pending_records if r.device_id))
        device_map = {}
        if device_ids:
            with self.get_session() as session:
                devices = session.query(DeviceDB).filter(
                    DeviceDB.id.in_(device_ids)
                ).all()
                # 需要在 session 内提取数据，避免 detached 问题
                for d in devices:
                    device_map[d.id] = d
                # 保持 session 打开以便后续使用
                session.expunge_all()
        
        # 3. 逐条发送
        for record in pending_records:
            try:
                device = device_map.get(record.device_id) if record.device_id else None
                
                if device:
                    print(f"[Notification] Sending pending notification {record.id} to device {device.id}")
                    await self._send_to_device(record, device)
                else:
                    print(f"[Notification] Device {record.device_id} not found for pending notification {record.id}")
                    record.status = NotificationStatus.FAILED
                    record.error_message = "Target device not found"
                    self._save_record(record)
                    
            except Exception as e:
                print(f"[Notification] Error processing pending record {record.id}: {e}")
                record.status = NotificationStatus.FAILED
                record.error_message = str(e)
                self._save_record(record)

    def get_notification_history(
        self,
        user_id: str,
        limit: int = 50
    ) -> List[NotificationRecord]:
        """Get notification history for a user"""
        self._ensure_initialized()
        with self.get_session() as session:
            records = session.query(NotificationRecordDB).filter(
                NotificationRecordDB.user_id == user_id
            ).order_by(
                NotificationRecordDB.created_at.desc()
            ).limit(limit).all()

            return [NotificationRecord(**r.to_dict()) for r in records]


# Global notification service instance
notification_service = NotificationService()
