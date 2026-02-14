import asyncio
import logging
import os
import signal
from dotenv import load_dotenv

# Load environment variables explicitly before importing app modules
# This is critical for Supervisor which might not load .env automatically
env_file = os.getenv("ENV_FILE", ".env")
print(f"[Scheduler] Loading environment from {env_file}")
load_dotenv(env_file)

from app.scheduler.background_tasks import task_scheduler

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

async def main():
    """Run the scheduler service"""
    logger.info("Starting UniLife Scheduler Service...")
    
    # Start the scheduler
    task_scheduler.start()
    
    # Handle shutdown signals
    stop_event = asyncio.Event()
    
    def handle_signal():
        stop_event.set()
    
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, handle_signal)
    
    logger.info("Scheduler Service Running via APScheduler")
    
    # Keep running until signal received
    await stop_event.wait()
    
    logger.info("Stopping Scheduler Service...")
    task_scheduler.stop()
    logger.info("Scheduler Service Halted")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        # Fallback if signal handler doesn't catch it
        pass
