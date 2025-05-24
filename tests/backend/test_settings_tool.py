import unittest
import os
import sys
import tempfile
import sqlite3

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from KITCore.database_manager import create_tables, get_db_connection
from KITCore.tools.settings_tool import (
    get_setting,
    set_setting,
    list_settings,
    delete_setting,
    DEFAULT_SETTINGS
)

class TestSettingsTool(unittest.TestCase):
    _test_db_handle = None
    _test_db_path = None
    _original_env_var = None

    @classmethod
    def setUpClass(cls):
        cls._original_env_var = os.environ.get('KIT_TEST_DB_PATH')
        cls._test_db_handle = tempfile.NamedTemporaryFile(suffix=".db", prefix="test_settings_db_", delete=False)
        cls._test_db_path = cls._test_db_handle.name
        cls._test_db_handle.close()
        os.environ['KIT_TEST_DB_PATH'] = cls._test_db_path
        if not create_tables():
            raise RuntimeError(f"Failed to create tables for settings test database: {cls._test_db_path}")

    @classmethod
    def tearDownClass(cls):
        if cls._test_db_path:
            try:
                os.remove(cls._test_db_path)
            except OSError as e:
                print(f"Error removing test settings database {cls._test_db_path}: {e}", file=sys.stderr)
        if cls._original_env_var is not None:
            os.environ['KIT_TEST_DB_PATH'] = cls._original_env_var
        elif 'KIT_TEST_DB_PATH' in os.environ:
            del os.environ['KIT_TEST_DB_PATH']

    def setUp(self):
        conn = get_db_connection()
        if conn is None:
            self.fail(f"Failed to get connection to settings test DB {self.__class__._test_db_path} in setUp")
        try:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM user_settings")
            conn.commit()
        except sqlite3.Error as e:
            self.fail(f"Database error during settings test setUp data clearing: {e}")
        finally:
            if conn:
                conn.close()

    def test_get_setting_non_existent_returns_default(self):
        self.assertEqual(get_setting("default_export_directory"), DEFAULT_SETTINGS["default_export_directory"])
        self.assertEqual(get_setting("default_purge_days"), DEFAULT_SETTINGS["default_purge_days"])
        self.assertIsNone(get_setting("non_existent_key"))

    def test_get_setting_with_override(self):
        self.assertEqual(get_setting("default_export_directory", default_override="/my/override"), "/my/override")
        self.assertIsNone(get_setting("non_existent_key", default_override=None))
        self.assertEqual(get_setting("non_existent_key", default_override="specific_default"), "specific_default")

    def test_set_and_get_setting(self):
        self.assertTrue(set_setting("default_export_directory", "/test/exports"))
        self.assertEqual(get_setting("default_export_directory"), "/test/exports")

        self.assertTrue(set_setting("ai_model_preference", "gemini-1.5-pro"))
        self.assertEqual(get_setting("ai_model_preference"), "gemini-1.5-pro")

    def test_set_and_get_default_purge_days(self):
        self.assertTrue(set_setting("default_purge_days", 30))
        self.assertEqual(get_setting("default_purge_days"), 30)

        self.assertTrue(set_setting("default_purge_days", 0))
        self.assertEqual(get_setting("default_purge_days"), 0)

        # Test setting to None (should be stored as empty string and retrieved as None)
        self.assertTrue(set_setting("default_purge_days", None))
        self.assertIsNone(get_setting("default_purge_days"))
        
        # Verify internal storage of None as empty string for default_purge_days
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT setting_value FROM user_settings WHERE setting_key = ?", ("default_purge_days",))
        row = cursor.fetchone()
        self.assertEqual(row['setting_value'], "")
        conn.close()

    def test_set_setting_invalid_key_still_stores_if_not_checked_in_tool(self):
        # The settings_tool.set_setting itself does not validate keys against DEFAULT_SETTINGS
        # Key validation is expected at a higher level (e.g., CLI handler)
        self.assertTrue(set_setting("my_custom_key", "my_value"))
        self.assertEqual(get_setting("my_custom_key"), "my_value") # It will be retrieved as is
        # However, list_settings will only show keys present in DEFAULT_SETTINGS or merged from DB

    def test_list_settings_empty_db_returns_defaults(self):
        settings = list_settings()
        self.assertEqual(settings, DEFAULT_SETTINGS)
        self.assertIsNone(settings.get("default_purge_days")) # Check specific type from default

    def test_list_settings_with_some_set(self):
        set_setting("default_export_directory", "/listed/exports")
        set_setting("default_purge_days", 45)

        settings = list_settings()
        self.assertEqual(settings["default_export_directory"], "/listed/exports")
        self.assertEqual(settings["default_purge_days"], 45)
        self.assertEqual(settings["ai_model_preference"], DEFAULT_SETTINGS["ai_model_preference"]) # Unset should be default

    def test_list_settings_all_defaults_after_deleting(self):
        set_setting("default_export_directory", "/tmp")
        self.assertTrue(delete_setting("default_export_directory"))
        settings = list_settings()
        self.assertEqual(settings["default_export_directory"], DEFAULT_SETTINGS["default_export_directory"])

    def test_delete_setting(self):
        set_setting("default_import_directory", "/to/delete")
        self.assertEqual(get_setting("default_import_directory"), "/to/delete")
        
        self.assertTrue(delete_setting("default_import_directory"))
        self.assertEqual(get_setting("default_import_directory"), DEFAULT_SETTINGS["default_import_directory"])

    def test_delete_non_existent_setting(self):
        # Deleting a non-existent setting should be successful (idempotent)
        self.assertTrue(delete_setting("this_key_does_not_exist_in_db_or_defaults"))
        self.assertIsNone(get_setting("this_key_does_not_exist_in_db_or_defaults"))

    def test_get_setting_type_conversion_fallback(self):
        # Manually insert a bad value for default_purge_days
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("INSERT OR REPLACE INTO user_settings (setting_key, setting_value) VALUES (?, ?)", ("default_purge_days", "not-an-int"))
        conn.commit()
        conn.close()
        # get_setting should return the default value for default_purge_days (None)
        self.assertIsNone(get_setting("default_purge_days"))

    def test_list_settings_type_conversion_fallback(self):
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("INSERT OR REPLACE INTO user_settings (setting_key, setting_value) VALUES (?, ?)", ("default_purge_days", "bad-val"))
        conn.commit()
        conn.close()

        settings = list_settings()
        self.assertIsNone(settings.get("default_purge_days")) # Should fall back to None default

if __name__ == '__main__':
    unittest.main() 