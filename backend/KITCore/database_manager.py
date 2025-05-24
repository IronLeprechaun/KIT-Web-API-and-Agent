import sqlite3
import os
import sys
import subprocess

# Add the parent directory of KITCore (which is backend) to sys.path
_current_dir = os.path.dirname(os.path.abspath(__file__)) # This is backend/KITCore
_backend_dir = os.path.dirname(_current_dir) # This should be backend
_project_root = os.path.dirname(_backend_dir) # This should be the project root

if _backend_dir not in sys.path:
    sys.path.insert(0, _backend_dir)

try:
    # Corrected import: directly from 'config' which is now findable in sys.path
    from config import KIT_DATABASE_PATH as DEFAULT_KIT_DATABASE_PATH, KIT_DATABASE_DIR as DEFAULT_KIT_DATABASE_DIR
except ImportError as e:
    print(f"ERROR: Could not import 'config.py'. Original error: {e}", file=sys.stderr)
    print(f"Ensure config.py is in {_backend_dir} and that directory is in sys.path.", file=sys.stderr)
    print(f"Current sys.path: {sys.path}", file=sys.stderr)
    # Provide default fallbacks or re-raise to make the failure explicit
    # For now, let's re-raise to clearly indicate the problem if config isn't found.
    raise

# config.py is in the project root.
# The main executable script (KITCore.py or test scripts) should ensure PROJECT_ROOT is in sys.path.
# from config import KIT_DATABASE_PATH as DEFAULT_KIT_DATABASE_PATH, KIT_DATABASE_DIR as DEFAULT_KIT_DATABASE_DIR # Old import

def _get_effective_db_path_and_dir():
    """Determines the database path and directory, prioritizing an environment variable for testing."""
    env_db_path = os.environ.get('KIT_TEST_DB_PATH')
    if env_db_path:
        # Ensure the path is absolute if a relative path is given via env var,
        # assuming it's relative to the project root for consistency if not absolute.
        # However, for testing, it's usually best to provide an absolute path.
        # For simplicity here, we'll assume the env var provides a usable path.
        db_path = env_db_path
        db_dir = os.path.dirname(db_path)
        # print(f"DEBUG: Using TEST database path from env var: {db_path}", file=sys.stderr) # For debugging tests
        return db_path, db_dir
    else:
        # print(f"DEBUG: Using DEFAULT database path: {DEFAULT_KIT_DATABASE_PATH}", file=sys.stderr) # For debugging
        return DEFAULT_KIT_DATABASE_PATH, DEFAULT_KIT_DATABASE_DIR

def get_db_connection():
    """Establishes and returns a SQLite database connection using the effective path."""
    db_path, db_dir = _get_effective_db_path_and_dir()
    try:
        if not os.path.exists(db_path):
            # This message is more relevant if we are *expecting* the default DB to exist.
            # For tests, the DB might be created on the fly.
            # Consider if this print is always appropriate or should be conditional.
            print(f"Database not found at {db_path}. Attempting to create directory if needed.", file=sys.stderr)

        # Ensure the directory exists, especially for test databases that might be in temp locations.
        if db_dir: # db_dir could be empty if db_path is just a filename in CWD.
             os.makedirs(db_dir, exist_ok=True)
        
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row # Access columns by name
        return conn
    except sqlite3.Error as e:
        print(f"Database connection error for {db_path}: {e}", file=sys.stderr)
        return None
    except OSError as e:
        print(f"OS error while ensuring database directory {db_dir} exists or connecting to {db_path}: {e}", file=sys.stderr)
        return None

def create_tables():
    """Creates the necessary tables in the database. Drops existing tables first to ensure a clean slate."""
    conn = None # Initialize conn to None for the finally block
    db_path, _ = _get_effective_db_path_and_dir() # Get current path for messages
    try:
        conn = get_db_connection()
        if conn is None:
            print(f"Cannot create tables for {db_path}: database connection failed.", file=sys.stderr)
            return False # Indicate failure

        cursor = conn.cursor()

        # Enable foreign key support for this connection (important for ON DELETE CASCADE if used, and general integrity)
        # For DROP TABLE, it's less critical but good practice to be aware of FKs.
        cursor.execute("PRAGMA foreign_keys = ON;")

        # Drop tables in an order that respects foreign key constraints
        # (child tables or tables referenced by others should be dropped first).
        cursor.execute("DROP TABLE IF EXISTS note_tags;")
        cursor.execute("DROP TABLE IF EXISTS notes;")
        cursor.execute("DROP TABLE IF EXISTS tags;")
        cursor.execute("DROP TABLE IF EXISTS user_settings;")
        
        print(f"Existing tables (if any) dropped in {db_path}.", file=sys.stdout) # Added for clarity during initdb

        # Notes Table (with versioning)
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS notes (
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

        # Tags Table
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS tags (
            tag_id INTEGER PRIMARY KEY AUTOINCREMENT,
            tag_type TEXT NOT NULL DEFAULT 'general',
            tag_value TEXT NOT NULL,
            UNIQUE (tag_type, tag_value)
        );
        """)

        # Note_Tags Junction Table
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS note_tags (
            note_version_id INTEGER NOT NULL,
            tag_id INTEGER NOT NULL,
            PRIMARY KEY (note_version_id, tag_id),
            FOREIGN KEY (note_version_id) REFERENCES notes(note_id),
            FOREIGN KEY (tag_id) REFERENCES tags(tag_id)
        );
        """)

        # User Settings Table
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS user_settings (
            setting_key TEXT PRIMARY KEY,
            setting_value TEXT
        );
        """)

        # --- Add Indexes for Performance ---
        print(f"Creating indexes in {db_path}...", file=sys.stdout)
        # Indexes for notes table
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_notes_latest_deleted_created ON notes (is_latest_version, is_deleted, created_at DESC);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_notes_original_note_id ON notes (original_note_id);")
        # Indexes for tags table
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_tags_type_value ON tags (tag_type, tag_value);")
        # Indexes for note_tags junction table (covered by PK, but explicit can sometimes help specific queries)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_note_tags_note_version_id ON note_tags (note_version_id);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_note_tags_tag_id ON note_tags (tag_id);")
        print(f"Indexes checked/created in {db_path}.", file=sys.stdout)
        # --- End Indexes ---

        conn.commit()
        print(f"Database tables checked/created at {db_path}") # Keep this stdout for CLI success
        return True # Indicate success
    except sqlite3.Error as e:
        print(f"Database error during table creation for {db_path}: {e}", file=sys.stderr)
        return False # Indicate failure
    except Exception as e: # Catch any other unexpected errors
        print(f"An unexpected error occurred during table creation for {db_path}: {e}", file=sys.stderr)
        return False # Indicate failure
    finally:
        if conn:
            conn.close()

def set_setting(key: str, value: str) -> bool:
    """Saves or updates a setting in the user_settings table. Returns True on success, False on error."""
    conn = None
    db_path, _ = _get_effective_db_path_and_dir()
    try:
        conn = get_db_connection()
        if conn is None:
            print(f"Cannot set setting '{key}' for {db_path}: database connection failed.", file=sys.stderr)
            return False
        cursor = conn.cursor()
        cursor.execute("INSERT OR REPLACE INTO user_settings (setting_key, setting_value) VALUES (?, ?)", (key, value))
        conn.commit()
        # print(f"Setting '{key}' saved.") # This is for CLI, KITCore.py will handle output
        return True
    except sqlite3.Error as e:
        print(f"Database error when setting setting '{key}' for {db_path}: {e}", file=sys.stderr)
        return False
    finally:
        if conn:
            conn.close()

def get_setting(key: str):
    """Retrieves a setting from the user_settings table. Returns value or None if not found/error."""
    conn = None
    db_path, _ = _get_effective_db_path_and_dir()
    try:
        conn = get_db_connection()
        if conn is None:
            print(f"Cannot get setting '{key}' for {db_path}: database connection failed.", file=sys.stderr)
            return None
        cursor = conn.cursor()
        cursor.execute("SELECT setting_value FROM user_settings WHERE setting_key = ?", (key,))
        row = cursor.fetchone()
        if row:
            return row['setting_value']
        # print(f"Setting '{key}' not found.") # Let caller decide how to handle not found
        return None
    except sqlite3.Error as e:
        print(f"Database error when getting setting '{key}' for {db_path}: {e}", file=sys.stderr)
        return None
    finally:
        if conn:
            conn.close()

if __name__ == '__main__':
    # This allows running this script directly to initialize the database
    db_path_for_direct_run, _ = _get_effective_db_path_and_dir()
    print(f"Attempting to initialize database directly using path: {db_path_for_direct_run}")
    if create_tables():
        print(f"Database initialized successfully from direct script run at {db_path_for_direct_run}.")
    else:
        print(f"Database initialization failed from direct script run at {db_path_for_direct_run}.", file=sys.stderr)
        sys.exit(1) # Exit with error code if direct run fails 