import sqlite3
import os
import sys
import json
from datetime import datetime

# --- Configuration ---
# Determine the project root so we can correctly path to the database and config
# This script is in backend/KITCore/tools/
# It's designed to be run from the project root (e.g., `python backend/KITCore/tools/migrate_db_typed_tags.py`)
# Path adjustment logic: (backend/KITCore/tools -> ../backend/KITCore -> ../backend -> ../PROJECT_ROOT)
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..', '..'))
# DB_DIR = os.path.join(PROJECT_ROOT, 'KIT_Web', 'backend', 'KITCore', 'database')
DB_DIR = os.path.join(PROJECT_ROOT, 'backend', 'KITCore', 'database')
CONFIG_PATH = os.path.join(PROJECT_ROOT, 'backend', 'config.py')

SOURCE_DB_NAME = 'kit_agent_backup_PRE_TYPED_TAGS.db' # IMPORTANT: Script will READ from this
TARGET_DB_NAME = 'kit_agent_MIGRATED.db' # Script will CREATE and WRITE to this

SOURCE_DB_PATH = os.path.join(DB_DIR, SOURCE_DB_NAME)
TARGET_DB_PATH = os.path.join(DB_DIR, TARGET_DB_NAME)

# Add backend directory to sys.path to allow finding 'config' if needed by copied functions,
# though for this standalone script, direct pathing is preferred.
BACKEND_DIR = os.path.join(PROJECT_ROOT, 'KIT_Web', 'backend')
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

# Add project root to sys.path to allow importing config
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

# --- Database Connection Functions ---
def get_db_connection(db_path):
    """Establishes and returns a SQLite database connection."""
    try:
        # Ensure the directory exists if it's for the target DB
        if db_path == TARGET_DB_PATH:
            os.makedirs(os.path.dirname(db_path), exist_ok=True)
        
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row # Access columns by name
        print(f"Successfully connected to database: {db_path}")
        return conn
    except sqlite3.Error as e:
        print(f"Database connection error for {db_path}: {e}", file=sys.stderr)
        return None
    except OSError as e:
        print(f"OS error while ensuring database directory for {db_path} exists or connecting: {e}", file=sys.stderr)
        return None

# --- Schema Creation for Target DB (Copied and adapted from database_manager.py) ---
def create_tables_in_target(conn):
    """Creates the necessary tables in the target database with the new schema."""
    db_path = TARGET_DB_PATH # For messages
    try:
        cursor = conn.cursor()
        cursor.execute("PRAGMA foreign_keys = OFF;") # Turn off for DDL initially

        # Drop tables if they exist (for a clean run of the script)
        cursor.execute("DROP TABLE IF EXISTS note_tags;")
        cursor.execute("DROP TABLE IF EXISTS notes;")
        cursor.execute("DROP TABLE IF EXISTS tags;")
        cursor.execute("DROP TABLE IF EXISTS user_settings;")
        print(f"Existing tables (if any) dropped in {db_path}.")

        # Notes Table (same as original)
        cursor.execute("""
        CREATE TABLE notes (
            note_id INTEGER PRIMARY KEY AUTOINCREMENT,
            original_note_id INTEGER,
            content TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            is_latest_version BOOLEAN NOT NULL CHECK (is_latest_version IN (0, 1)),
            properties_json TEXT,
            is_deleted BOOLEAN DEFAULT 0 NOT NULL CHECK (is_deleted IN (0, 1)),
            deleted_at TIMESTAMP,
            FOREIGN KEY (original_note_id) REFERENCES notes(note_id)
        );
        """)

        # Tags Table (NEW SCHEMA with type and value)
        cursor.execute("""
        CREATE TABLE tags (
            tag_id INTEGER PRIMARY KEY AUTOINCREMENT,
            tag_type TEXT NOT NULL DEFAULT 'general',
            tag_value TEXT NOT NULL,
            UNIQUE (tag_type, tag_value)
        );
        """)

        # Note_Tags Junction Table (same as original)
        cursor.execute("""
        CREATE TABLE note_tags (
            note_version_id INTEGER NOT NULL,
            tag_id INTEGER NOT NULL,
            PRIMARY KEY (note_version_id, tag_id),
            FOREIGN KEY (note_version_id) REFERENCES notes(note_id) ON DELETE CASCADE,
            FOREIGN KEY (tag_id) REFERENCES tags(tag_id) ON DELETE CASCADE
        );
        """)
        # Added ON DELETE CASCADE for robustness during migration steps if re-run/cleaned.

        # User Settings Table (same as original)
        cursor.execute("""
        CREATE TABLE user_settings (
            setting_key TEXT PRIMARY KEY,
            setting_value TEXT
        );
        """)
        
        conn.commit()
        cursor.execute("PRAGMA foreign_keys = ON;") # Turn back on
        print(f"Database tables created successfully in {db_path}")
        return True
    except sqlite3.Error as e:
        print(f"Database error during table creation for {db_path}: {e}", file=sys.stderr)
        if conn: conn.rollback()
        return False
    except Exception as e:
        print(f"An unexpected error occurred during table creation for {db_path}: {e}", file=sys.stderr)
        if conn: conn.rollback()
        return False

# --- Migration Logic Placeholder ---
def migrate_data(source_conn, target_conn):
    print("Starting data migration...")
    source_cursor = source_conn.cursor()
    target_cursor = target_conn.cursor()

    # Turn off foreign keys for the duration of data insertion in target
    target_cursor.execute("PRAGMA foreign_keys = OFF;")
    target_conn.commit()


    # 1. Migrate Tags
    print("Migrating tags...")
    source_cursor.execute("SELECT tag_id, tag_name FROM tags") # Old schema
    old_tags = source_cursor.fetchall()
    
    old_to_new_tag_id_map = {}
    new_tag_id_counter = 1 # Simple counter if not relying on AUTOINCREMENT during this phase for mapping

    for old_tag in old_tags:
        old_tag_id = old_tag['tag_id']
        old_tag_name = old_tag['tag_name'].strip().lower()
        
        # Default to 'general' type for all old tags
        tag_type = 'general'
        tag_value = old_tag_name

        try:
            target_cursor.execute("INSERT INTO tags (tag_type, tag_value) VALUES (?, ?)", (tag_type, tag_value))
            new_tag_id = target_cursor.lastrowid
            if new_tag_id is not None:
                 old_to_new_tag_id_map[old_tag_id] = new_tag_id
            else: # Should not happen if insert is successful
                print(f"Warning: Failed to get new_tag_id for old_tag_id {old_tag_id} ('{tag_type}':'{tag_value}') after insert. Attempting select.", file=sys.stderr)
                target_cursor.execute("SELECT tag_id FROM tags WHERE tag_type = ? AND tag_value = ?", (tag_type, tag_value))
                refetched_tag = target_cursor.fetchone()
                if refetched_tag:
                    old_to_new_tag_id_map[old_tag_id] = refetched_tag['tag_id']
                else:
                    print(f"CRITICAL: Still could not get new_tag_id for '{tag_type}':'{tag_value}'. Skipping tag id mapping for old_id {old_tag_id}", file=sys.stderr)

        except sqlite3.IntegrityError: # Unique constraint (tag_type, tag_value) violated
            # This means this (type, value) combination was already inserted (e.g. from a differently-cased old tag that normalized to the same)
            print(f"Warning: Tag '{tag_type}':'{tag_value}' (from old_id {old_tag_id}) already exists. Mapping to existing new tag.", file=sys.stderr)
            target_cursor.execute("SELECT tag_id FROM tags WHERE tag_type = ? AND tag_value = ?", (tag_type, tag_value))
            existing_tag = target_cursor.fetchone()
            if existing_tag:
                old_to_new_tag_id_map[old_tag_id] = existing_tag['tag_id']
            else:
                print(f"CRITICAL: Could not find existing tag '{tag_type}':'{tag_value}' after integrity error. Skipping mapping for old_id {old_tag_id}", file=sys.stderr)
    target_conn.commit() # Commit tags
    print(f"Finished migrating tags. {len(old_to_new_tag_id_map)} tags mapped.")


    # 2. Migrate Notes (Assuming schema is identical for notes table structure)
    print("Migrating notes...")
    # Get all columns from source notes table to be safe
    source_cursor.execute("PRAGMA table_info(notes)")
    notes_columns = [col['name'] for col in source_cursor.fetchall()]
    notes_columns_str = ", ".join(notes_columns)
    placeholders = ", ".join(["?"] * len(notes_columns))

    source_cursor.execute(f"SELECT {notes_columns_str} FROM notes")
    all_notes = source_cursor.fetchall()
    
    notes_to_insert = []
    for note_row in all_notes:
        notes_to_insert.append(tuple(note_row))

    if notes_to_insert:
        target_cursor.executemany(f"INSERT INTO notes ({notes_columns_str}) VALUES ({placeholders})", notes_to_insert)
    target_conn.commit() # Commit notes
    print(f"Finished migrating {len(all_notes)} notes.")

    # 3. Migrate Note-Tag Relationships
    print("Migrating note-tag relationships...")
    source_cursor.execute("SELECT note_version_id, tag_id FROM note_tags") # Old schema
    old_note_tags = source_cursor.fetchall()
    
    new_note_tags_to_insert = []
    skipped_relations_count = 0
    for old_relation in old_note_tags:
        old_note_version_id = old_relation['note_version_id']
        old_tag_id = old_relation['tag_id']
        
        new_tag_id = old_to_new_tag_id_map.get(old_tag_id)
        
        if new_tag_id is not None:
            # Note IDs (note_version_id) are assumed to be the same as they are auto-incrementing
            # and we inserted all notes preserving their original IDs.
            new_note_tags_to_insert.append((old_note_version_id, new_tag_id))
        else:
            print(f"Warning: Could not find new_tag_id for old_tag_id {old_tag_id} when migrating note_tags. Skipping relation for note_version_id {old_note_version_id}.", file=sys.stderr)
            skipped_relations_count +=1
            
    if new_note_tags_to_insert:
        target_cursor.executemany("INSERT INTO note_tags (note_version_id, tag_id) VALUES (?, ?)", new_note_tags_to_insert)
    target_conn.commit() # Commit note_tags
    print(f"Finished migrating {len(new_note_tags_to_insert)} note-tag relationships. Skipped {skipped_relations_count} due to unmapped tags.")

    # 4. Migrate User Settings (Assuming schema is identical)
    print("Migrating user settings...")
    source_cursor.execute("SELECT setting_key, setting_value FROM user_settings")
    all_settings = source_cursor.fetchall()
    
    settings_to_insert = []
    for setting_row in all_settings:
        settings_to_insert.append(tuple(setting_row))
        
    if settings_to_insert:
        target_cursor.executemany("INSERT OR REPLACE INTO user_settings (setting_key, setting_value) VALUES (?, ?)", settings_to_insert)
    target_conn.commit() # Commit settings
    print(f"Finished migrating {len(all_settings)} user settings.")

    # Re-enable foreign keys
    target_cursor.execute("PRAGMA foreign_keys = ON;")
    target_conn.commit()
    
    # Optional: Integrity Check
    target_cursor.execute("PRAGMA foreign_key_check;")
    fk_violations = target_cursor.fetchall()
    if fk_violations:
        print(f"WARNING: Foreign key violations detected after migration: {fk_violations}", file=sys.stderr)
    else:
        print("Foreign key check passed successfully on target database.")

    print("Data migration completed.")


# --- Main Execution ---
if __name__ == '__main__':
    print(f"Migration Script: Typed Tags")
    print(f"Source DB: {SOURCE_DB_PATH}")
    print(f"Target DB: {TARGET_DB_PATH}")

    if not os.path.exists(SOURCE_DB_PATH):
        print(f"ERROR: Source database '{SOURCE_DB_PATH}' does not exist. Please ensure you have backed up your original kit_agent.db to this name or update SOURCE_DB_NAME.", file=sys.stderr)
        sys.exit(1)

    if os.path.exists(TARGET_DB_PATH):
        user_confirm = input(f"WARNING: Target database '{TARGET_DB_PATH}' already exists and will be overwritten. Continue? (yes/no): ")
        if user_confirm.lower() != 'yes':
            print("Migration aborted by user.")
            sys.exit(0)
        else:
            try:
                os.remove(TARGET_DB_PATH)
                print(f"Removed existing target database: {TARGET_DB_PATH}")
            except OSError as e:
                print(f"Error removing existing target database {TARGET_DB_PATH}: {e}", file=sys.stderr)
                sys.exit(1)

    source_conn = get_db_connection(SOURCE_DB_PATH)
    target_conn = get_db_connection(TARGET_DB_PATH)

    if source_conn is None or target_conn is None:
        print("Failed to establish database connections. Aborting migration.", file=sys.stderr)
        if source_conn: source_conn.close()
        if target_conn: target_conn.close()
        sys.exit(1)

    try:
        if not create_tables_in_target(target_conn):
            print("Failed to create tables in target database. Aborting.", file=sys.stderr)
            sys.exit(1)
        
        migrate_data(source_conn, target_conn)
        print(f"Migration successful. New database is at: {TARGET_DB_PATH}")
        print(f"Please verify the data in '{TARGET_DB_NAME}' and then, if correct, you can manually replace your original '{os.path.basename(KIT_DATABASE_PATH)}' with it.")
        print(f"(Original path was: {os.path.join(DB_DIR, os.path.basename(KIT_DATABASE_PATH))})")

    except Exception as e:
        print(f"An error occurred during the migration process: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc(file=sys.stderr)
    finally:
        if source_conn:
            source_conn.close()
        if target_conn:
            target_conn.close()
            
    print("Migration script finished.") 