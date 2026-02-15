"""
UniLife Backend - Main Application
"""
import os
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.api import chat, events, users, snapshots, stats, auth, sync, devices, notifications, habits, projects
from app.utils.logger import init_logging, LogColors

# 延迟导入后台任务调度器（Serverless 环境下不需要）
task_scheduler = None
if not os.getenv("SERVERLESS"):
    from app.scheduler.background_tasks import task_scheduler


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager"""
    # 初始化日志系统
    init_logging()

    import logging
    logger = logging.getLogger("main")

    # Startup
    logger.info(f"{LogColors.bold('🚀 UniLife Backend starting...')}")
    logger.info(f"🔧 Debug mode: {settings.debug}")

    # Initialize database
    from app.services.db import db_service
    try:
        db_service.initialize()
        logger.info("✅ Database initialized successfully")
    except Exception as e:
        logger.error(f"❌ Database initialization failed: {e}")

    # 检测运行环境
    is_serverless = os.getenv("SERVERLESS")
    if is_serverless:
        logger.info(f"{LogColors.bold('☁️ Running in Serverless mode (background tasks disabled)')}")
    else:
        logger.info(f"🌐 API listening on http://{settings.api_host}:{settings.api_port}")

    # Start background task scheduler (非 Serverless 环境)
    if not is_serverless and task_scheduler:
        task_scheduler.start()

    # Start habit replenishment scheduler
    if not is_serverless:
        from app.tasks.habit_replenishment import start_scheduler
        try:
            start_scheduler()
        except Exception as e:
            logger.warning(f"Failed to start habit replenishment scheduler: {e}")

    yield

    # Shutdown
    logger.info("🛑 UniLife Backend shutting down...")
    # Stop background task scheduler (非 Serverless 环境)
    if not is_serverless and task_scheduler:
        task_scheduler.stop()


# Create FastAPI application
app = FastAPI(
    title="UniLife Backend API",
    description="AI-powered life scheduling assistant",
    version="0.1.0",
    lifespan=lifespan,
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if settings.debug else [],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(auth.router)  # Auth router already has prefix in its definition
app.include_router(chat.router, prefix="/api/v1", tags=["Chat"])
app.include_router(events.router, prefix="/api/v1", tags=["Events"])
app.include_router(users.router, prefix="/api/v1", tags=["Users"])
app.include_router(snapshots.router, prefix="/api/v1", tags=["Snapshots"])
app.include_router(stats.router, prefix="/api/v1", tags=["Stats"])
app.include_router(sync.router, prefix="/api/v1", tags=["Sync"])
app.include_router(devices.router, prefix="/api/v1", tags=["Devices"])
app.include_router(notifications.router, prefix="/api/v1", tags=["Notifications"])
app.include_router(habits.router, prefix="/api/v1", tags=["Habits"])
app.include_router(projects.router, prefix="/api/v1/projects", tags=["Projects"])


@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "name": "UniLife Backend",
        "version": "0.1.0",
        "status": "running",
    }


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=settings.debug,
        log_level=settings.log_level.lower(),
    )
