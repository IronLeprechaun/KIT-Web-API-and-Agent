import sys
import os
from typing import Any, Dict, List

# Adjust path for KITCore imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from KITCore.tools.settings_tool import (
    get_setting as kit_get_setting,
    set_setting as kit_set_setting,
    list_settings as kit_list_settings,
    delete_setting as kit_delete_setting,
    DEFAULT_SETTINGS
)

class SettingsService:
    @staticmethod
    async def get_all_settings() -> Dict[str, Any]:
        """Retrieves all settings."""
        try:
            # kit_list_settings() returns a dict of settings
            return kit_list_settings()
        except Exception as e:
            # Log e
            raise Exception(f"Failed to retrieve all settings: {str(e)}")

    @staticmethod
    async def get_setting(key: str) -> Any:
        """Retrieves a specific setting by its key."""
        if key not in DEFAULT_SETTINGS:
            raise ValueError(f"Invalid setting key: {key}")
        try:
            # kit_get_setting returns the value of the setting or its default if not set
            return kit_get_setting(key)
        except Exception as e:
            # Log e
            raise Exception(f"Failed to retrieve setting '{key}': {str(e)}")

    @staticmethod
    async def set_setting(key: str, value: Any) -> Any:
        """Sets the value of a specific setting."""
        if key not in DEFAULT_SETTINGS:
            raise ValueError(f"Invalid setting key: {key}")
        
        # Validate value type based on DEFAULT_SETTINGS definition
        expected_type = type(DEFAULT_SETTINGS[key]['default'])
        # Allow None for settings that can be None
        if DEFAULT_SETTINGS[key]['default'] is None and value is not None:
             pass # Allow any type if default is None and value is being set (user might clear it later)
        elif value is not None and not isinstance(value, expected_type):
            # Attempt to cast if possible (e.g., string to int for default_purge_days)
            try:
                if expected_type == int and isinstance(value, str) and value.isdigit():
                    value = int(value)
                elif expected_type == bool and isinstance(value, str) and value.lower() in ['true', 'false', 'yes', 'no', '1', '0']:
                    value = value.lower() in ['true', 'yes', '1']
                # Add more specific type casting rules as needed
                else:
                    raise TypeError(f"Invalid value type for '{key}'. Expected {expected_type.__name__}, got {type(value).__name__}.")
            except ValueError:
                 raise TypeError(f"Could not convert value for '{key}' to {expected_type.__name__}.")

        try:
            # kit_set_setting should handle the storage and return the set value or confirm success.
            # Assuming it returns the value that was set.
            kit_set_setting(key, value)
            return value # Return the value that was intended to be set
        except Exception as e:
            # Log e
            raise Exception(f"Failed to set setting '{key}': {str(e)}")

    @staticmethod
    async def delete_setting(key: str) -> None:
        """Deletes a specific setting, reverting it to its default value."""
        if key not in DEFAULT_SETTINGS:
            raise ValueError(f"Invalid setting key: {key}")
        try:
            kit_delete_setting(key)
            # No explicit return value needed, action is to delete.
            # The route can then fetch the new (default) value to confirm.
        except Exception as e:
            # Log e
            raise Exception(f"Failed to delete setting '{key}': {str(e)}") 