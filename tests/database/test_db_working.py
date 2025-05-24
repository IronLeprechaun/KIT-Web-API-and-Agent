#!/usr/bin/env python3
"""
Working Database Test
Database test that correctly handles module imports.
"""

import sqlite3
import sys
import os
from pathlib import Path

# Set up proper paths
current_file = Path(__file__).resolve()
tests_dir = current_file.parent  # tests/database
kit_web_dir = tests_dir.parent.parent  # KIT_Web directory  
backend_dir = kit_web_dir / "backend"

# Add backend to path and change to backend directory
sys.path.insert(0, str(backend_dir))
original_cwd = os.getcwd()
os.chdir(str(backend_dir))

try:
    from KITCore.database_manager import get_db_connection
    print("✅ Database import successful")
except ImportError as e:
    print(f"❌ Failed to import database modules: {e}")
    sys.exit(1)

def test_connection_and_schema():
    """Test database connection and basic schema"""
    print("🔌 Testing database connection and schema...")
    
    try:
        conn = get_db_connection()
        if conn is None:
            print("❌ Failed to get database connection")
            return False
        
        cursor = conn.cursor()
        
        # Test basic connection
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = cursor.fetchall()
        table_names = [table[0] for table in tables]
        
        print(f"✅ Database connection successful, found {len(tables)} tables")
        
        # Check for required tables
        required_tables = ['notes', 'tags', 'note_tags']
        missing_tables = [table for table in required_tables if table not in table_names]
        
        if missing_tables:
            print(f"❌ Missing required tables: {missing_tables}")
            conn.close()
            return False
        
        print("✅ All required tables found")
        
        # Test a simple query
        cursor.execute("SELECT COUNT(*) FROM notes")
        note_count = cursor.fetchone()[0]
        print(f"✅ Database has {note_count} notes")
        
        conn.close()
        return True
        
    except Exception as e:
        print(f"❌ Database test failed: {e}")
        return False

def main():
    """Run the test"""
    try:
        success = test_connection_and_schema()
        print(f"\n{'✅' if success else '❌'} Database test {'PASSED' if success else 'FAILED'}")
        return success
    finally:
        # Restore original working directory
        os.chdir(original_cwd)

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1) 