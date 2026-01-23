#!/usr/bin/env python3
"""
Database Migration: Add User Diary and Profile Analysis Tables

This migration adds:
1. user_diaries - Daily observation diaries
2. profile_analysis_logs - Profile analysis execution logs

Run this after the existing migrations.
"""
import sqlite3
import sys
from pathlib import Path

# Get the database path
DB_PATH = "unilife.db"

def migrate():
    """Execute the migration"""
    print(f"[Migration] Starting diary tables migration...")
    print(f"[Migration] Database: {DB_PATH}")

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    try:
        # Check if migration already ran
        cursor.execute("""
            SELECT name FROM sqlite_master
            WHERE type='table' AND name='user_diaries'
        """)
        if cursor.fetchone():
            print("[Migration] user_diaries table already exists, skipping...")
            return

        # Create user_diaries table
        print("[Migration] Creating user_diaries table...")
        cursor.execute("""
            CREATE TABLE user_diaries (
                id VARCHAR PRIMARY KEY,
                user_id VARCHAR NOT NULL,

                -- Diary content
                diary_date DATE NOT NULL,
                summary TEXT NOT NULL,
                key_insights JSON,
                extracted_signals JSON,

                -- Daily statistics
                conversation_count INTEGER DEFAULT 0,
                message_count INTEGER DEFAULT 0,
                tool_calls_count INTEGER DEFAULT 0,

                -- Timestamps
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,

                -- Unique constraint: one diary per user per day
                UNIQUE (user_id, diary_date)
            );
        """)

        # Create profile_analysis_logs table
        print("[Migration] Creating profile_analysis_logs table...")
        cursor.execute("""
            CREATE TABLE profile_analysis_logs (
                id VARCHAR PRIMARY KEY,
                user_id VARCHAR NOT NULL,

                -- Job information
                job_type VARCHAR NOT NULL,
                analysis_period_start DATETIME,
                analysis_period_end DATETIME,

                -- Analysis results
                diary_ids_analyzed JSON,
                profile_changes JSON,
                confidence_delta JSON,

                -- Status tracking
                status VARCHAR DEFAULT 'pending',
                error_message TEXT,

                -- Timestamps
                started_at DATETIME,
                completed_at DATETIME,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            );
        """)

        # Create indexes
        print("[Migration] Creating indexes...")
        cursor.execute("""
            CREATE INDEX idx_user_diaries_user_id ON user_diaries(user_id);
        """)

        cursor.execute("""
            CREATE INDEX idx_user_diaries_date ON user_diaries(diary_date);
        """)

        cursor.execute("""
            CREATE INDEX idx_user_diaries_user_date ON user_diaries(user_id, diary_date);
        """)

        cursor.execute("""
            CREATE INDEX idx_profile_analysis_user_id ON profile_analysis_logs(user_id);
        """)

        cursor.execute("""
            CREATE INDEX idx_profile_analysis_status ON profile_analysis_logs(status);
        """)

        cursor.execute("""
            CREATE INDEX idx_profile_analysis_job_type ON profile_analysis_logs(job_type);
        """)

        conn.commit()

        print("[Migration] Migration completed successfully!")
        print("[Migration] Created tables:")
        print("  - user_diaries")
        print("  - profile_analysis_logs")
        print("[Migration] Created indexes for efficient queries")

    except Exception as e:
        conn.rollback()
        print(f"[Migration] Error: {e}")
        sys.exit(1)
    finally:
        conn.close()


def verify():
    """Verify the migration"""
    print("\n[Verification] Checking tables...")

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    try:
        # Check user_diaries
        cursor.execute("""
            SELECT COUNT(*) FROM user_diaries
        """)
        diary_count = cursor.fetchone()[0]
        print(f"  - user_diaries: {diary_count} rows")

        # Check profile_analysis_logs
        cursor.execute("""
            SELECT COUNT(*) FROM profile_analysis_logs
        """)
        log_count = cursor.fetchone()[0]
        print(f"  - profile_analysis_logs: {log_count} rows")

        # Check indexes
        cursor.execute("""
            SELECT name FROM sqlite_master
            WHERE type='index' AND tbl_name='user_diaries'
        """)
        diary_indexes = [row[0] for row in cursor.fetchall()]
        print(f"  - user_diaries indexes: {len(diary_indexes)}")

        cursor.execute("""
            SELECT name FROM sqlite_master
            WHERE type='index' AND tbl_name='profile_analysis_logs'
        """)
        log_indexes = [row[0] for row in cursor.fetchall()]
        print(f"  - profile_analysis_logs indexes: {len(log_indexes)}")

        print("[Verification] Complete!")

    except Exception as e:
        print(f"[Verification] Error: {e}")
    finally:
        conn.close()


if __name__ == "__main__":
    migrate()
    verify()
