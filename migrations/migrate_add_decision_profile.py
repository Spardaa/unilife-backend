"""
Migration: Add user_decision_profiles table

This migration creates the user_decision_profiles table for storing
user decision preferences (separate from the personality profile in UserProfile).

Run: python migrations/migrate_add_decision_profile.py
"""
from datetime import datetime
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from app.config import settings


def migrate():
    """Run the migration"""
    # Get database path
    db_path = settings.database_url.replace("sqlite:///", "")

    print(f"[Migration] Database: {db_path}")

    # Create engine
    engine = create_engine(
        f"sqlite:///{db_path}",
        connect_args={"check_same_thread": False}
    )

    # Create table
    print("[Migration] Creating user_decision_profiles table...")

    with engine.connect() as conn:
        # Create the table
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS user_decision_profiles (
                id TEXT PRIMARY KEY,
                user_id TEXT UNIQUE NOT NULL,
                time_preference TEXT,
                meeting_preference TEXT,
                energy_profile TEXT,
                conflict_resolution TEXT,
                scenario_preferences TEXT,
                explicit_rules TEXT,
                confidence_scores TEXT,
                created_at TIMESTAMP NOT NULL,
                updated_at TIMESTAMP NOT NULL
            )
        """))

        # Create indexes
        conn.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_user_decision_profiles_user_id
            ON user_decision_profiles(user_id)
        """))

        conn.commit()

    print("[Migration] Table created successfully.")

    # Create default profiles for existing users
    print("[Migration] Creating default profiles for existing users...")
    session_maker = sessionmaker(bind=engine)
    session = session_maker()

    try:
        # Get existing users
        result = session.execute(text("SELECT DISTINCT user_id FROM events"))
        user_ids = [row[0] for row in result]

        if user_ids:
            print(f"[Migration] Found {len(user_ids)} existing users")

            # Get existing users with decision profiles
            result = session.execute(text("SELECT user_id FROM user_decision_profiles"))
            existing_user_ids = {row[0] for row in result}

            # Create default profiles for users who don't have one
            from app.models.user_decision_profile import UserDecisionProfile

            for user_id in user_ids:
                if user_id not in existing_user_ids:
                    # Create default profile
                    profile = UserDecisionProfile(user_id=user_id)

                    # Insert into database
                    from app.models.user_decision_profile import UserDecisionProfileDB
                    db_profile = UserDecisionProfileDB.from_profile(profile)

                    session.execute(text("""
                        INSERT INTO user_decision_profiles (
                            id, user_id, time_preference, meeting_preference,
                            energy_profile, conflict_resolution, scenario_preferences,
                            explicit_rules, confidence_scores, created_at, updated_at
                        ) VALUES (
                            :id, :user_id, :time_preference, :meeting_preference,
                            :energy_profile, :conflict_resolution, :scenario_preferences,
                            :explicit_rules, :confidence_scores, :created_at, :updated_at
                        )
                    """), {
                        "id": db_profile.id,
                        "user_id": db_profile.user_id,
                        "time_preference": db_profile.time_preference,
                        "meeting_preference": db_profile.meeting_preference,
                        "energy_profile": db_profile.energy_profile,
                        "conflict_resolution": db_profile.conflict_resolution,
                        "scenario_preferences": db_profile.scenario_preferences,
                        "explicit_rules": db_profile.explicit_rules,
                        "confidence_scores": db_profile.confidence_scores,
                        "created_at": db_profile.created_at,
                        "updated_at": db_profile.updated_at
                    })

            session.commit()
            print(f"[Migration] Created {len(user_ids) - len(existing_user_ids)} default profiles")
        else:
            print("[Migration] No existing users found")

    except Exception as e:
        session.rollback()
        print(f"[Migration] Error creating default profiles: {e}")
        raise
    finally:
        session.close()

    print("[Migration] Complete!")


if __name__ == "__main__":
    migrate()
