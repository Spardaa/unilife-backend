"""
Application Configuration
"""
import os
from typing import Optional
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables"""

    model_config = SettingsConfigDict(
        env_file=os.getenv("ENV_FILE", ".env"),
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # API Configuration
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    debug: bool = False

    # Database Configuration
    db_type: str = "sqlite"  # sqlite, postgresql
    sqlite_path: str = "unilife.db"  # SQLite database file path

    # PostgreSQL Configuration (optional, for future migration)
    postgresql_url: Optional[str] = None

    # Supabase Configuration (optional, for future use)
    supabase_url: Optional[str] = None
    supabase_key: Optional[str] = None
    supabase_service_key: Optional[str] = None

    # LLM Configuration (GLM)
    glm_api_key: str
    glm_base_url: str = "https://open.bigmodel.cn/api/paas/v4/"
    glm_model: str = "glm-4.7-flash"

    # JWT Configuration
    jwt_secret_key: str
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 10080  # 7 days

    # WeChat Integration
    wechat_webhook_url: Optional[str] = None
    wechat_secret_key: Optional[str] = None

    # APNs Push Notification Configuration
    apns_key_id: Optional[str] = None          # Apple Push Notification Key ID
    apns_team_id: Optional[str] = None         # Apple Developer Team ID
    apns_key_path: Optional[str] = None        # Path to .p8 key file
    apns_bundle_id: Optional[str] = None       # App bundle identifier
    apns_use_sandbox: bool = True              # Use sandbox (development) or production

    # Logging
    log_level: str = "INFO"

    @property
    def database_url(self) -> str:
        """Get database URL based on db_type"""
        if self.db_type == "sqlite":
            return f"sqlite:///{self.sqlite_path}"
        elif self.db_type == "postgresql" and self.postgresql_url:
            return self.postgresql_url
        else:
            return f"sqlite:///{self.sqlite_path}"


# Global settings instance
settings = Settings()
