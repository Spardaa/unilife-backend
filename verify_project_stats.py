
import asyncio
import sys
import os
import uuid
import datetime

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.services.db import db_service

async def verify_stats():
    user_id = "test_user_verification"
    project_id = str(uuid.uuid4())
    
    print(f"🚀 Starting Verification for Project: {project_id}")
    
    # 1. Create Project
    print("1️⃣ Creating Project...")
    project_data = {
        "id": project_id,
        "user_id": user_id,
        "title": "Verification Project",
        "description": "Test Stats"
    }
    await db_service.create_project(project_data)
    
    # 2. Create One-Off Task
    print("2️⃣ Creating One-Off Task...")
    task_data = {
        "user_id": user_id,
        "title": "One Off Task",
        "project_id": project_id,
        "status": "PENDING"
    }
    await db_service.create_event(task_data)
    
    # 3. Create Routine Template
    print("3️⃣ Creating Routine Template...")
    template_data = {
        "user_id": user_id,
        "title": "Routine Template",
        "project_id": project_id,
        "is_template": True,
        "repeat_pattern": {"type": "daily"}
    }
    template = await db_service.create_event(template_data)
    
    # 4. Create Routine Instance
    print("4️⃣ Creating Routine Instance...")
    instance_data = {
        "user_id": user_id,
        "title": "Routine Instance",
        "project_id": project_id,
        "parent_event_id": template["id"], # Link to template
        "status": "COMPLETED",
        "is_template": False
    }
    await db_service.create_event(instance_data)
    
    # 5. Check Project Stats
    print("5️⃣ Checking Project Stats...")
    project = await db_service.get_project(project_id, user_id)
    
    print(f"📊 Stats Result:")
    print(f"   - Total One-Off Tasks: {project.get('one_off_tasks_total')}")
    print(f"   - Completed One-Off Tasks: {project.get('one_off_tasks_completed')}")
    
    # Verification Logic
    success = True
    if project.get('one_off_tasks_total') != 1:
        print("❌ FAILED: Total tasks should be 1 (only the one-off task)")
        success = False
    else:
        print("✅ SUCCESS: Total tasks count is correct (excluded routine instance)")
        
    if project.get('one_off_tasks_completed') != 0:
        print("❌ FAILED: Completed tasks should be 0 (the one-off task is PENDING)")
        success = False
    else:
        print("✅ SUCCESS: Completed tasks count is correct (excluded completed routine instance)")
        
    # Cleanup (Optional, but good for local DB)
    # await db_service.delete_project(project_id, user_id)
    
    if success:
        print("\n🎉 ALL VERIFICATION PASSED")
    else:
        print("\n⚠️ VERIFICATION FAILED")

if __name__ == "__main__":
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(verify_stats())
