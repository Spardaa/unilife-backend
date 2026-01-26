"""
Database Initialization Script

Run this script to initialize the database with sample data
"""
import sys
import os
import asyncio

# Add app directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.services.db import db_service
from app.models.user import User
import uuid


async def init_database():
    """Initialize database and create sample user"""
    print("=" * 50)
    print("UniLife Database Initialization")
    print("=" * 50)

    # Initialize database (create tables)
    db_service.initialize()
    print("\n✓ Database tables created")

    # Also create routine tables
    from app.models.routine import Base as RoutineBase
    from app.models.user_decision_profile import Base as DecisionProfileBase
    from sqlalchemy import create_engine
    from app.config import settings
    engine = create_engine(settings.database_url)
    RoutineBase.metadata.create_all(bind=engine)
    print("✓ Routine tables created")
    DecisionProfileBase.metadata.create_all(bind=engine)
    print("✓ Decision profile tables created")

    # Create a sample user
    sample_user_id = str(uuid.uuid4())

    user_data = {
        "id": sample_user_id,
        "email": "demo@unilife.com",
        "nickname": "Demo User",
        "timezone": "Asia/Shanghai",
        "energy_profile": {
            "hourly_baseline": {
                "6": 40, "7": 50, "8": 70, "9": 80, "10": 90, "11": 85,
                "12": 70, "13": 65, "14": 60, "15": 70, "16": 75, "17": 65,
                "18": 60, "19": 55, "20": 50, "21": 40, "22": 30, "23": 20
            },
            "task_energy_cost": {
                "deep_work": -20,
                "meeting": -10,
                "study": -15,
                "break": +15,
                "coffee": +10,
                "sleep": +100
            },
            "learned_adjustments": {}
        },
        "current_energy": 85,
        "preferences": {
            "notification_enabled": True,
            "auto_schedule_enabled": True,
            "energy_based_scheduling": True,
            "working_hours_start": 9,
            "working_hours_end": 18
        }
    }

    try:
        created_user = await db_service.create_user(user_data)
        print(f"\n✓ Sample user created:")
        print(f"  - ID: {created_user['id']}")
        print(f"  - Email: {created_user['email']}")
        print(f"  - Nickname: {created_user['nickname']}")
        print(f"  - Current Energy: {created_user['current_energy']}")
    except Exception as e:
        print(f"\n✗ Error creating user: {e}")
        print("  (User might already exist)")

    # Create sample events
    from datetime import datetime, timedelta

    sample_events = [
        {
            "user_id": sample_user_id,
            "title": "团队周会",
            "description": "讨论本周项目进度",
            "start_time": datetime.now() + timedelta(days=1, hours=14),
            "end_time": datetime.now() + timedelta(days=1, hours=15),
            "duration": 60,
            "energy_required": "MEDIUM",
            "urgency": 4,
            "importance": 4,
            "is_deep_work": False,
            "event_type": "schedule",
            "category": "WORK",
            "tags": ["weekly", "meeting"],
            "location": "会议室A",
            "participants": [sample_user_id],
            "status": "PENDING",
            "created_by": "user",
            "ai_confidence": 0.8
        },
        {
            "user_id": sample_user_id,
            "title": "完成课程设计",
            "description": "完成本学期课程设计项目",
            "end_time": datetime.now() + timedelta(days=5, hours=23, minutes=59),
            "duration": 180,
            "energy_required": "HIGH",
            "urgency": 5,
            "importance": 5,
            "is_deep_work": True,
            "event_type": "deadline",
            "category": "STUDY",
            "tags": ["project", "deadline"],
            "status": "PENDING",
            "created_by": "user",
            "ai_confidence": 0.7
        },
        {
            "user_id": sample_user_id,
            "title": "健身房锻炼",
            "description": "每周三次锻炼",
            "duration": 60,
            "energy_required": "LOW",
            "urgency": 2,
            "importance": 3,
            "is_deep_work": False,
            "event_type": "floating",
            "category": "HEALTH",
            "tags": ["exercise", "gym"],
            "location": "健身房",
            "status": "PENDING",
            "created_by": "user",
            "ai_confidence": 0.6
        }
    ]

    for event_data in sample_events:
        try:
            created_event = await db_service.create_event(event_data)
            print(f"\n✓ Sample event created:")
            print(f"  - ID: {created_event['id']}")
            print(f"  - Title: {created_event['title']}")
            print(f"  - Type: {created_event.get('event_type', 'N/A')}")
            start = created_event.get('start_time')
            end = created_event.get('end_time')
            print(f"  - Time: {start} - {end}")
        except Exception as e:
            print(f"\n✗ Error creating event: {e}")

    print("\n" + "=" * 50)
    print("Database initialization complete!")
    print("=" * 50)
    print(f"\nSample User ID: {sample_user_id}")
    print("Use this ID to test the API")
    print("\nStart the server:")
    print("  python -m app.main")
    print("or")
    print("  uvicorn app.main:app --reload")


if __name__ == "__main__":
    asyncio.run(init_database())
