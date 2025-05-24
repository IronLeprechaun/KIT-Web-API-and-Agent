import sqlite3
import json
import sys # For stderr printing, can be removed if logging is used exclusively
from typing import Optional, Any, Dict

from ..database_manager import get_db_connection

# Default values for settings if not found in the database.
# This can be expanded as more settings are defined.
DEFAULT_SETTINGS = {
    "default_export_directory": "",
    "default_import_directory": "",
    "ai_model_preference": "gemini-1.0-pro", # Assuming this is a sensible default
    "default_purge_days": None, # No default, CLI argument remains mandatory unless set
    "date_display_format": "%Y-%m-%d %H:%M:%S",
    "last_auto_purge_date": "", # Stores YYYY-MM-DD of last auto purge
}

def get_setting(key: str, default_override: Optional[Any] = None) -> Optional[Any]:
    """
    Retrieves a setting value from the user_settings table.
    Handles type conversion for known settings.
    
    Args:
        key: The name of the setting to retrieve.
        default_override: A value to return if the setting is not found,
                          overriding the globally defined DEFAULT_SETTINGS.

    Returns:
        The value of the setting, or the default_override if provided,
        or the value from DEFAULT_SETTINGS, or None if not found and no default.
    """
    conn = None
    try:
        conn = get_db_connection()
        if conn is None:
            print(f"Database connection not available in get_setting.", file=sys.stderr)
            # Fallback to defaults if DB is unavailable
            if default_override is not None:
                return default_override
            return DEFAULT_SETTINGS.get(key)

        cursor = conn.cursor()
        cursor.execute("SELECT setting_value FROM user_settings WHERE setting_key = ?", (key,))
        row = cursor.fetchone()

        if row:
            value_str = row['setting_value']
            # Handle type conversions for specific known keys
            if key == "default_purge_days":
                try:
                    return int(value_str) if value_str else None
                except ValueError:
                    print(f"Warning: Could not convert setting '{key}' value '{value_str}' to int. Returning default.", file=sys.stderr)
                    return DEFAULT_SETTINGS.get(key) # Or specific default for this key
            # Add other type conversions here if needed, e.g., for boolean settings
            # if key == "some_boolean_setting":
            #     return value_str.lower() == 'true'
            return value_str # Most settings might be stored and used as strings
        else:
            # Setting not in DB, use default_override or DEFAULT_SETTINGS
            if default_override is not None:
                return default_override
            return DEFAULT_SETTINGS.get(key)

    except sqlite3.Error as e:
        print(f"Database error in get_setting for key '{key}': {e}", file=sys.stderr)
        # Fallback to defaults on error
        if default_override is not None:
            return default_override
        return DEFAULT_SETTINGS.get(key)
    except Exception as e:
        print(f"Unexpected error in get_setting for key '{key}': {e}", file=sys.stderr)
        if default_override is not None:
            return default_override
        return DEFAULT_SETTINGS.get(key)
    finally:
        if conn:
            conn.close()

def set_setting(key: str, value: Any) -> bool:
    """
    Sets or updates a setting in the user_settings table.
    The value will be stored as a string.

    Args:
        key: The name of the setting to set.
        value: The value of the setting. Will be converted to string for storage.

    Returns:
        True if the setting was successfully set, False otherwise.
    """
    conn = None
    try:
        conn = get_db_connection()
        if conn is None:
            print(f"Database connection not available in set_setting.", file=sys.stderr)
            return False
        
        cursor = conn.cursor()
        # Convert value to string for consistent storage.
        # Specific type handling (like for 'None' for default_purge_days) can be done here or before calling.
        value_str = str(value)
        if value is None and key == "default_purge_days": # Special handling for nullable int
             value_str = "" # Store as empty string to represent None for int after retrieval

        cursor.execute(
            "INSERT OR REPLACE INTO user_settings (setting_key, setting_value) VALUES (?, ?)",
            (key, value_str)
        )
        conn.commit()
        return cursor.rowcount > 0

    except sqlite3.Error as e:
        print(f"Database error in set_setting for key '{key}': {e}", file=sys.stderr)
        if conn:
            conn.rollback()
        return False
    except Exception as e:
        print(f"Unexpected error in set_setting for key '{key}': {e}", file=sys.stderr)
        if conn:
            conn.rollback()
        return False
    finally:
        if conn:
            conn.close()

def list_settings() -> Dict[str, Any]:
    """
    Retrieves all settings stored in the user_settings table.
    Combines stored settings with global defaults for any missing keys.
    Handles type conversion for known settings.

    Returns:
        A dictionary of all settings (key: value).
    """
    settings_from_db: Dict[str, Any] = {}
    conn = None
    try:
        conn = get_db_connection()
        if conn is None:
            print(f"Database connection not available in list_settings. Returning defaults.", file=sys.stderr)
            # Return a copy of default settings if DB is not available
            # Perform type conversions on default values as get_setting would
            processed_defaults = {}
            for k, v_default in DEFAULT_SETTINGS.items():
                if k == "default_purge_days" and isinstance(v_default, str): # Should be None or int
                     processed_defaults[k] = int(v_default) if v_default else None
                # Add other type conversions if DEFAULT_SETTINGS stores them differently than runtime type
                else:
                     processed_defaults[k] = v_default
            return processed_defaults

        cursor = conn.cursor()
        cursor.execute("SELECT setting_key, setting_value FROM user_settings")
        rows = cursor.fetchall()

        for row in rows:
            key, value_str = row['setting_key'], row['setting_value']
            # Apply same type conversion logic as in get_setting
            if key == "default_purge_days":
                try:
                    settings_from_db[key] = int(value_str) if value_str else None
                except ValueError:
                    print(f"Warning: Could not convert setting '{key}' value '{value_str}' to int in list_settings. Using default.", file=sys.stderr)
                    settings_from_db[key] = DEFAULT_SETTINGS.get(key)
            # Add other type conversions here
            # elif key == "some_boolean_setting":
            #    settings_from_db[key] = value_str.lower() == 'true'
            else:
                settings_from_db[key] = value_str
        
        # Merge with defaults: defaults provide base, DB values override
        # Start with a copy of all defined DEFAULT_SETTINGS to ensure all are present
        final_settings = {}
        for k, v_default in DEFAULT_SETTINGS.items():
             final_settings[k] = settings_from_db.get(k, v_default) # Use DB value if present, else default

        return final_settings

    except sqlite3.Error as e:
        print(f"Database error in list_settings: {e}", file=sys.stderr)
        # Fallback to defaults on error
        processed_defaults = {}
        for k, v_default in DEFAULT_SETTINGS.items():
            if k == "default_purge_days" and isinstance(v_default, str):
                    processed_defaults[k] = int(v_default) if v_default else None
            else:
                    processed_defaults[k] = v_default
        return processed_defaults
    except Exception as e:
        print(f"Unexpected error in list_settings: {e}", file=sys.stderr)
        processed_defaults = {}
        for k, v_default in DEFAULT_SETTINGS.items():
            if k == "default_purge_days" and isinstance(v_default, str):
                    processed_defaults[k] = int(v_default) if v_default else None
            else:
                    processed_defaults[k] = v_default
        return processed_defaults
    finally:
        if conn:
            conn.close()

def delete_setting(key: str) -> bool:
    """
    Deletes a setting from the user_settings table.
    This effectively reverts the setting to its default value upon next get.

    Args:
        key: The name of the setting to delete.

    Returns:
        True if the setting was successfully deleted or didn't exist, False on error.
    """
    conn = None
    try:
        conn = get_db_connection()
        if conn is None:
            print(f"Database connection not available in delete_setting.", file=sys.stderr)
            return False
        
        cursor = conn.cursor()
        cursor.execute("DELETE FROM user_settings WHERE setting_key = ?", (key,))
        conn.commit()
        # cursor.rowcount will be 0 if key didn't exist, 1 if it did.
        # We consider it a success even if key was not present.
        return True 

    except sqlite3.Error as e:
        print(f"Database error in delete_setting for key '{key}': {e}", file=sys.stderr)
        if conn:
            conn.rollback()
        return False
    except Exception as e:
        print(f"Unexpected error in delete_setting for key '{key}': {e}", file=sys.stderr)
        if conn:
            conn.rollback()
        return False
    finally:
        if conn:
            conn.close() 