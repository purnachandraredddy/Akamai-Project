#!/usr/bin/env python3
"""
Database migration management script
"""

import asyncio
import os
import sys
from pathlib import Path

# Add the project root to the Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from alembic.config import Config
from alembic import command
from app.config import settings


def run_migration(command_name: str, *args):
    """Run an Alembic migration command"""
    # Set up Alembic configuration
    alembic_cfg = Config(str(project_root / "alembic.ini"))
    
    # Override the database URL for migrations
    alembic_cfg.set_main_option("sqlalchemy.url", settings.database_url_computed)
    
    # Run the command
    if command_name == "upgrade":
        command.upgrade(alembic_cfg, *args)
    elif command_name == "downgrade":
        command.downgrade(alembic_cfg, *args)
    elif command_name == "revision":
        command.revision(alembic_cfg, *args)
    elif command_name == "current":
        command.current(alembic_cfg, *args)
    elif command_name == "history":
        command.history(alembic_cfg, *args)
    elif command_name == "stamp":
        command.stamp(alembic_cfg, *args)
    else:
        print(f"Unknown command: {command_name}")
        sys.exit(1)


def main():
    """Main entry point for database migration script"""
    if len(sys.argv) < 2:
        print("Usage: python scripts/db_migrate.py <command> [args...]")
        print("Commands:")
        print("  upgrade [revision]     - Upgrade to a revision (default: head)")
        print("  downgrade [revision]   - Downgrade to a revision (default: -1)")
        print("  revision -m 'message'  - Create a new revision")
        print("  current               - Show current revision")
        print("  history               - Show migration history")
        print("  stamp [revision]      - Stamp database with a revision")
        sys.exit(1)
    
    command_name = sys.argv[1]
    args = sys.argv[2:] if len(sys.argv) > 2 else []
    
    try:
        run_migration(command_name, *args)
        print(f"✅ Migration command '{command_name}' completed successfully")
    except Exception as e:
        print(f"❌ Migration command '{command_name}' failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
