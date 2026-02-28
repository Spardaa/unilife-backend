import asyncio
import json
import logging
from datetime import datetime
import os
import sys

# Ensure this is running in the correct directory context
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.services.db import db_service
from app.api.events import get_events

logging.basicConfig(level=logging.INFO)

async def test_get_events_virtual_expansion():
    print("Initializing Database...")
    db_service._ensure_initialized()
    
    with db_service.get_session() as session:
        from app.services.db import EventModel
        
        # We need a user ID to test with.
        # Check if there are any users or just pick the first user with events
        sample_event = session.query(EventModel).first()
        if not sample_event:
            print("No events found in database to test with.")
            return
            
        user_id = sample_event.user_id
        
        # Find a project ID that has at least one recurring template
        project_templates = session.query(EventModel).filter(
            EventModel.user_id == user_id,
            EventModel.is_template == True,
            EventModel.project_id.isnot(None)
        ).all()
        
        if not project_templates:
            print(f"No templates with project_id found for user {user_id}.")
            return
            
        test_project_id = project_templates[0].project_id
        
        print(f"\n--- Testing get_events with project_id={test_project_id} ---")
        
        # Test the API logic directly (bypassing FastAPI routing)
        try:
            # We don't have Depends(get_current_user) so we pass user_id directly
            # Note: We need to mock the endpoint's behavior or call db_service directly if testing the endpoint is hard
            
            # Since get_events API endpoint is async and expects Depends injection which might be tricky,
            # Let's test the inner logic that we modified
            filters = {"project_id": test_project_id}
            
            # 1. Get real instances
            print("1. Getting regular events...")
            instances = await db_service.get_events(
                user_id=user_id,
                filters=filters,
                limit=100
            )
            
            # 2. Get templates (this is what we just fixed)
            print("2. Getting templates with filters...")
            templates = await db_service.get_recurring_templates(
                user_id=user_id,
                filters=filters
            )
            
            print(f"\nFound {len(instances)} real instances for project.")
            print(f"Found {len(templates)} templates for project.")
            
            # Check for contamination
            contamination = False
            for t in templates:
                if t.get('project_id') != test_project_id:
                    print(f"❌ CONTAMINATION FOUND: Template {t.get('id')} has project_id={t.get('project_id')} but we filtered for {test_project_id}")
                    contamination = True
                    
            if not contamination:
                print("✅ Success: All returned templates belong to the correct project.")
                
            # Verify that db_service.get_recurring_templates without filter still returns more/all
            all_templates = await db_service.get_recurring_templates(user_id=user_id)
            print(f"Without filters, found {len(all_templates)} total templates for user.")
            
            if len(all_templates) > len(templates):
                print("✅ Confirmed: Filter is correctly limiting the scope of templates returned.")
            else:
                print("Note: User only has templates in this one project, or filter matched all templates. Try creating a template in another project to fully verify.")
                
        except Exception as e:
            print(f"Error during test: {e}")

if __name__ == "__main__":
    asyncio.run(test_get_events_virtual_expansion())
