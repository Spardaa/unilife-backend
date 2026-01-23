"""
UniLife Backend - Main Application
"""
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.api import chat, events, users, snapshots, stats, diaries
from app.scheduler.background_tasks import task_scheduler
from app.utils.logger import init_logging, LogColors


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
    logger.info(f"🌐 API listening on http://{settings.api_host}:{settings.api_port}")

    # Start background task scheduler
    task_scheduler.start()

    yield

    # Shutdown
    logger.info("🛑 UniLife Backend shutting down...")
    # Stop background task scheduler
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
app.include_router(chat.router, prefix="/api/v1", tags=["Chat"])
app.include_router(events.router, prefix="/api/v1", tags=["Events"])
app.include_router(users.router, prefix="/api/v1", tags=["Users"])
app.include_router(snapshots.router, prefix="/api/v1", tags=["Snapshots"])
app.include_router(stats.router, prefix="/api/v1", tags=["Stats"])
app.include_router(diaries.router, prefix="/api/v1/diaries", tags=["Diaries"])


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
