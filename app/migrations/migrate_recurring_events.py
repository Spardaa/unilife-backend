"""
Migration Script: Convert Existing Recurring Event Instances to Template-Based Architecture

This script migrates existing recurring event data to the new lazy instance creation architecture.

OLD ARCHITECTURE:
- Habit events: 21 pre-generated instances with shared routine_batch_id
- Routine events: 90 pre-generated instances with parent_event_id

NEW ARCHITECTURE:
- Only template events are created
- Instances are created on-demand when user marks complete or edits
- Client-side virtual expansion for display

MIGRATION STEPS:
1. Find all recurring event instances (with parent_routine_id or routine_batch_id)
2. Group instances by their parent template
3. Create or update template events from the first instance of each group
4. Clean up instances:
   - Keep completed instances (for history)
   - Delete uncompleted instances older than 7 days
   - Keep recent uncompleted instances (will be converted to real on first interaction)

USAGE:
    python -m app.migrations.migrate_recurring_events [--dry-run] [--execute]

    --dry-run:    Show what would be done without making changes
    --execute:    Actually execute the migration (required to make changes)
"""
import sys
import os
from datetime import datetime, timedelta, date
from typing import Dict, List, Any, Optional

# Add parent directory to path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from app.services.db import db_service
from app.config import settings


class RecurringEventMigration:
    """Migration handler for recurring events"""

    def __init__(self, dry_run: bool = False):
        self.dry_run = dry_run
        self.stats = {
            "templates_created": 0,
            "templates_updated": 0,
            "instances_deleted": 0,
            "instances_kept": 0,
            "groups_processed": 0
        }

    def log(self, message: str):
        """Print log message with timestamp"""
        prefix = "[DRY RUN]" if self.dry_run else "[MIGRATION]"
        print(f"{prefix} {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - {message}")

    def get_all_recurring_instances(self) -> List[Dict[str, Any]]:
        """Get all instances that are part of recurring events"""
        self.log("Fetching all recurring event instances...")

        # Get all events and filter for those with parent relationships
        all_events = db_service.get_events(
            user_id=None,  # Get all users' events
            limit=10000
        )

        recurring_instances = []
        for event in all_events:
            # Check if this is an instance (has parent_routine_id or routine_batch_id)
            if event.get("parent_routine_id") or event.get("routine_batch_id"):
                # Exclude templates themselves
                if not event.get("is_template"):
                    recurring_instances.append(event)

        self.log(f"Found {len(recurring_instances)} recurring instances")
        return recurring_instances

    def group_instances_by_parent(self, instances: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
        """Group instances by their parent template or batch"""
        self.log("Grouping instances by parent...")

        grouped = {}

        for instance in instances:
            # Try parent_routine_id first (routine instances)
            parent_id = instance.get("parent_routine_id")

            # If no parent_routine_id, use routine_batch_id (habit instances)
            if not parent_id:
                parent_id = instance.get("routine_batch_id")

            if parent_id:
                if parent_id not in grouped:
                    grouped[parent_id] = []
                grouped[parent_id].append(instance)

        self.log(f"Found {len(grouped)} distinct recurring event groups")
        return grouped

    def create_template_from_instance(self, instance: Dict[str, Any]) -> str:
        """
        Create a template event from the first instance of a recurring group.

        Returns the template ID.
        """
        self.log(f"Creating template from instance: {instance['id']}")

        # Build template data from the instance
        template_data = {
            "user_id": instance["user_id"],
            "title": instance["title"],
            "description": instance.get("description"),
            "notes": instance.get("notes"),
            "event_type": instance["event_type"],
            "category": instance["category"],
            "tags": instance.get("tags", []),
            "location": instance.get("location"),
            "participants": instance.get("participants", []),
            "duration": instance.get("duration"),
            "time_period": instance.get("time_period"),
            "urgency": instance.get("urgency", 3),
            "importance": instance.get("importance", 3),
            "is_deep_work": instance.get("is_deep_work", False),
            "is_physically_demanding": instance.get("is_physically_demanding", False),
            "is_mentally_demanding": instance.get("is_mentally_demanding", False),
            "energy_consumption": instance.get("energy_consumption"),
            "status": "PENDING",
            "created_by": "migration",
            "ai_confidence": 1.0,
            "is_template": True,
            "parent_event_id": None,
            "repeat_pattern": None,
            "habit_interval": None
        }

        # Determine repeat pattern based on how instances were created
        if instance.get("routine_batch_id"):
            # This is a habit event - check for interval
            # For now, use daily pattern for habits
            template_data["repeat_pattern"] = {
                "type": "daily"
            }

            # Extract time from start_time if available
            if instance.get("start_time"):
                start_time = instance["start_time"]
                if isinstance(start_time, datetime):
                    template_data["repeat_pattern"]["time"] = start_time.strftime("%H:%M")

        # If the parent already exists, it might be a template - update it instead
        parent_id = instance.get("parent_routine_id")
        if parent_id:
            # Check if parent exists and is a template
            try:
                existing = db_service.get_event(parent_id, instance["user_id"])
                if existing and existing.get("is_template"):
                    self.log(f"Found existing template: {parent_id}, updating...")
                    if not self.dry_run:
                        # Update the template if needed
                        db_service.update_event(
                            event_id=parent_id,
                            user_id=instance["user_id"],
                            update_data=template_data
                        )
                    self.stats["templates_updated"] += 1
                    return parent_id
            except:
                pass

        # Create new template
        if not self.dry_run:
            template = db_service.create_event(template_data)
            self.stats["templates_created"] += 1
            return template["id"]
        else:
            self.stats["templates_created"] += 1
            return "dry-run-template-id"

    def cleanup_instances(self, instances: List[Dict[str, Any]], template_id: str) -> int:
        """
        Clean up instances after creating template.
        - Keep completed instances (for history)
        - Delete uncompleted instances older than 7 days
        """
        deleted_count = 0
        kept_count = 0
        cutoff_date = datetime.now() - timedelta(days=7)

        for instance in instances:
            should_delete = False
            reason = ""

            if instance.get("status") == "COMPLETED":
                # Keep completed instances
                should_delete = False
                reason = "completed - keeping for history"
            elif instance.get("status") == "CANCELLED":
                # Delete cancelled instances
                should_delete = True
                reason = "cancelled"
            else:
                # Check if uncompleted instance is old
                instance_date = instance.get("event_date") or instance.get("created_at")
                if instance_date:
                    if isinstance(instance_date, str):
                        instance_date = datetime.fromisoformat(instance_date.replace('Z', '+00:00'))

                    if instance_date < cutoff_date:
                        should_delete = True
                        reason = f"old uncompleted (from {instance_date.date()})"
                    else:
                        should_delete = False
                        reason = f"recent uncompleted (from {instance_date.date()}) - keeping"

            if should_delete:
                if not self.dry_run:
                    db_service.delete_event(instance["id"], instance["user_id"])
                deleted_count += 1
                self.log(f"  Deleting instance {instance['id']}: {reason}")
            else:
                kept_count += 1
                self.log(f"  Keeping instance {instance['id']}: {reason}")

        self.stats["instances_deleted"] += deleted_count
        self.stats["instances_kept"] += kept_count

        return deleted_count

    def migrate_group(self, parent_id: str, instances: List[Dict[str, Any]]) -> bool:
        """Migrate a single group of recurring instances"""
        self.log(f"\nProcessing group: {parent_id} ({len(instances)} instances)")

        # Sort instances by date, keep the first one as reference
        sorted_instances = sorted(
            instances,
            key=lambda x: (x.get("event_date") or x.get("created_at") or datetime.min)
        )

        first_instance = sorted_instances[0]

        # Create or update template
        template_id = self.create_template_from_instance(first_instance)
        self.log(f"Template ID: {template_id}")

        # Clean up instances
        deleted = self.cleanup_instances(instances, template_id)
        self.log(f"Deleted {deleted} instances, kept {len(instances) - deleted}")

        self.stats["groups_processed"] += 1
        return True

    def run(self) -> bool:
        """Execute the migration"""
        self.log("=" * 60)
        self.log("Starting recurring events migration")
        self.log("=" * 60)

        try:
            # Step 1: Get all recurring instances
            instances = self.get_all_recurring_instances()

            if not instances:
                self.log("No recurring instances found. Migration complete.")
                return True

            # Step 2: Group by parent
            grouped = self.group_instances_by_parent(instances)

            if not grouped:
                self.log("No groups found. Migration complete.")
                return True

            # Step 3: Process each group
            for parent_id, group_instances in grouped.items():
                try:
                    self.migrate_group(parent_id, group_instances)
                except Exception as e:
                    self.log(f"ERROR processing group {parent_id}: {e}")
                    import traceback
                    traceback.print_exc()
                    continue

            # Print summary
            self.log("\n" + "=" * 60)
            self.log("Migration Summary:")
            self.log(f"  Groups processed: {self.stats['groups_processed']}")
            self.log(f"  Templates created: {self.stats['templates_created']}")
            self.log(f"  Templates updated: {self.stats['templates_updated']}")
            self.log(f"  Instances deleted: {self.stats['instances_deleted']}")
            self.log(f"  Instances kept: {self.stats['instances_kept']}")
            self.log("=" * 60)

            if self.dry_run:
                self.log("DRY RUN COMPLETE - No changes were made")
                self.log("Run with --execute to apply changes")
            else:
                self.log("MIGRATION COMPLETE")

            return True

        except Exception as e:
            self.log(f"FATAL ERROR: {e}")
            import traceback
            traceback.print_exc()
            return False


def main():
    """Main entry point"""
    import argparse

    parser = argparse.ArgumentParser(
        description="Migrate recurring events to template-based architecture"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be done without making changes"
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Actually execute the migration"
    )

    args = parser.parse_args()

    # Default to dry run for safety
    dry_run = not args.execute

    if dry_run:
        print("Running in DRY RUN mode. Use --execute to apply changes.")
    else:
        print("Running in EXECUTE mode. Changes will be made to the database.")
        response = input("Are you sure you want to proceed? (yes/no): ")
        if response.lower() != "yes":
            print("Migration cancelled.")
            return

    # Initialize database
    try:
        db_service.initialize()
    except Exception as e:
        print(f"ERROR: Failed to initialize database: {e}")
        sys.exit(1)

    # Run migration
    migration = RecurringEventMigration(dry_run=dry_run)
    success = migration.run()

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
