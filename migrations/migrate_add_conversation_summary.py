"""
Migration: Add conversation_summaries table

This migration adds support for the rolling summary mechanism.
Run this migration after the basic migrations have been set up.

Usage:
    python migrations/migrate_add_conversation_summary.py
"""
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import create_engine, text
from app.config import settings
from app.models.conversation_summary import ConversationSummary


def migrate():
    """Run the migration"""
    print("Adding conversation_summaries table...")

    # Create engine
    engine = create_engine(settings.database_url, echo=True)


    # Create table
    ConversationSummary.__table__.create(engine, checkfirst=True)

    print("Migration completed: conversation_summaries table created.")


if __name__ == "__main__":
    migrate()
