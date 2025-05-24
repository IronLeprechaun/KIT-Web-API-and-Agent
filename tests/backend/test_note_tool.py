import unittest
import sqlite3
import os
import sys
import json
from datetime import datetime, timedelta, timezone # Added for new tests
import tempfile # For temporary test database

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

# Now that PROJECT_ROOT is in sys.path and KITCore is a package, these should work:
from config import KIT_DATABASE_PATH, KIT_DATABASE_DIR # config.py is at PROJECT_ROOT
from KITCore.database_manager import create_tables, get_db_connection
from KITCore.tools.note_tool import (
    create_note, find_notes, update_note, get_note_history,
    soft_delete_note, restore_note, get_deleted_notes, purge_deleted_notes, # Added soft delete functions
    export_all_notes, import_notes_from_json_data, # Added export/import functions
    add_tag_to_note, remove_tag_from_note, list_all_tags # Added list_all_tags
)

class TestNoteTool(unittest.TestCase):
    _test_db_handle = None
    _test_db_path = None
    _original_env_var = None # To store original env var if it existed

    @classmethod
    def setUpClass(cls):
        """Set up a temporary, isolated database for all tests in this class."""
        # Store if the env var was already set, to restore it later
        cls._original_env_var = os.environ.get('KIT_TEST_DB_PATH')

        # Create a temporary database file
        # tempfile.NamedTemporaryFile creates a file and returns a file object.
        # We need the name, and it should be deleted on close by default on some systems,
        # so we delete=False and manage deletion ourselves in tearDownClass.
        cls._test_db_handle = tempfile.NamedTemporaryFile(suffix=".db", prefix="test_kit_db_", delete=False)
        cls._test_db_path = cls._test_db_handle.name
        cls._test_db_handle.close() # Close it so sqlite3 can open it
        
        os.environ['KIT_TEST_DB_PATH'] = cls._test_db_path
        # print(f"DEBUG TestNoteTool: Using test DB: {cls._test_db_path}") # For test debugging

        if not create_tables():
            raise RuntimeError(f"Failed to create tables for test database: {cls._test_db_path}")

    @classmethod
    def tearDownClass(cls):
        """Clean up the temporary database and restore environment."""
        if cls._test_db_path:
            # print(f"DEBUG TestNoteTool: Removing test DB: {cls._test_db_path}") # For test debugging
            try:
                os.remove(cls._test_db_path)
            except OSError as e:
                print(f"Error removing test database {cls._test_db_path}: {e}", file=sys.stderr)
        
        # Restore or remove the environment variable
        if cls._original_env_var is not None:
            os.environ['KIT_TEST_DB_PATH'] = cls._original_env_var
        elif 'KIT_TEST_DB_PATH' in os.environ:
            del os.environ['KIT_TEST_DB_PATH']

    def setUp(self):
        """Clean up database tables before each test method."""
        # With setUpClass creating the DB, setUp just needs to clear tables.
        # The connection will use the path from KIT_TEST_DB_PATH set in setUpClass.
        conn = get_db_connection()
        if conn is None:
            self.fail(f"Failed to get connection to test DB {self.__class__._test_db_path} in setUp")
        try:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM note_tags")
            cursor.execute("DELETE FROM notes")
            cursor.execute("DELETE FROM tags")
            cursor.execute("DELETE FROM user_settings")
            # Reset autoincrement counters for SQLite
            cursor.execute("DELETE FROM sqlite_sequence WHERE name IN ('notes', 'tags');")
            conn.commit()
        except sqlite3.Error as e:
            self.fail(f"Database error during setUp data clearing: {e}")
        finally:
            if conn:
                conn.close()

    def test_create_simple_note(self):
        note_id = create_note(content="A simple test note.")
        self.assertIsNotNone(note_id, "Should return a note ID")

        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM notes WHERE note_id = ?", (note_id,))
        note_row = cursor.fetchone()
        conn.close()

        self.assertIsNotNone(note_row)
        self.assertEqual(note_row['content'], "A simple test note.")
        self.assertEqual(note_row['original_note_id'], note_id)
        self.assertEqual(note_row['is_latest_version'], 1)

    def test_create_note_with_tags(self):
        tags = ["python", "testing", "  ExampleTag  "]
        note_id = create_note(content="Note with tags.", tags_list=tags)
        self.assertIsNotNone(note_id)

        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT t.tag_name FROM tags t JOIN note_tags nt ON t.tag_id = nt.tag_id WHERE nt.note_version_id = ? ORDER BY t.tag_name", (note_id,))
        db_tags = [row['tag_name'] for row in cursor.fetchall()]
        conn.close()

        self.assertEqual(len(db_tags), 3)
        self.assertIn("python", db_tags)
        self.assertIn("testing", db_tags)
        self.assertIn("exampletag", db_tags)

    def test_create_note_with_properties(self):
        properties = {"priority": "high", "status": "pending"}
        note_id = create_note(content="Note with properties.", properties_dict=properties)
        self.assertIsNotNone(note_id)

        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT properties_json FROM notes WHERE note_id = ?", (note_id,))
        note_row = cursor.fetchone()
        conn.close()

        self.assertIsNotNone(note_row)
        self.assertIsNotNone(note_row['properties_json'])
        retrieved_props = json.loads(note_row['properties_json'])
        self.assertEqual(retrieved_props, properties)

    def test_find_notes_no_criteria(self):
        create_note(content="Note A")
        create_note(content="Note B")
        found_notes = find_notes()
        # Each note creates a version, so 2 notes = 2 latest versions
        self.assertEqual(len(found_notes), 2) 

    def test_find_notes_by_tag(self):
        create_note(content="Python intro", tags_list=["python", "beginner"])
        create_note(content="Java intro", tags_list=["java", "beginner"])
        create_note(content="Advanced Python", tags_list=["python", "advanced"])

        python_notes = find_notes(tags=["python"])
        self.assertEqual(len(python_notes), 2)
        for note in python_notes:
            self.assertIn("python", note['tags'])

        beginner_notes = find_notes(tags=["beginner"])
        self.assertEqual(len(beginner_notes), 2)

        advanced_python_notes = find_notes(tags=["python", "advanced"])
        self.assertEqual(len(advanced_python_notes), 1)
        self.assertEqual(advanced_python_notes[0]['content'], "Advanced Python")

    def test_find_notes_by_content_keyword(self):
        create_note(content="This is about apples and oranges.")
        create_note(content="Another note about apples.")
        create_note(content="Bananas are great.")

        apple_notes = find_notes(content_keywords=["apples"])
        self.assertEqual(len(apple_notes), 2)

        orange_notes = find_notes(content_keywords=["oranges"])
        self.assertEqual(len(orange_notes), 1)
        self.assertEqual(orange_notes[0]['content'], "This is about apples and oranges.")
    
    def test_find_notes_by_tag_and_content(self):
        create_note(content="Learning Python for scripting", tags_list=["python", "scripting"])
        create_note(content="Python for data science", tags_list=["python", "data"])
        create_note(content="General scripting tips", tags_list=["scripting", "tips"])

        python_scripting_notes = find_notes(tags=["python"], content_keywords=["scripting"])
        self.assertEqual(len(python_scripting_notes), 1)
        self.assertEqual(python_scripting_notes[0]['content'], "Learning Python for scripting")

    def test_find_notes_non_existent_tag(self):
        create_note(content="Some note")
        found_notes = find_notes(tags=["nonexistent"])
        self.assertEqual(len(found_notes), 0)

    def test_find_notes_date_range(self):
        import time
        # It's better to use a fixed, known date string format that SQLite expects (YYYY-MM-DD HH:MM:SS)
        # Create a note, then immediately fetch its creation time for the query.
        note_id = create_note(content="Timed note for date range test")
        self.assertIsNotNone(note_id)

        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT created_at FROM notes WHERE note_id = ?", (note_id,))
        created_at_row = cursor.fetchone()
        conn.close()
        self.assertIsNotNone(created_at_row)
        created_at_str = created_at_row['created_at']
        
        # Query for notes created exactly at this timestamp
        notes_in_range = find_notes(date_range=(created_at_str, created_at_str))
        self.assertTrue(any(n['note_id'] == note_id for n in notes_in_range), 
                        f"Note ID {note_id} not found in range {created_at_str}-{created_at_str}")

        # Test finding no notes before a very early date
        notes_before = find_notes(date_range=(None, "1970-01-01 00:00:00"))
        self.assertEqual(len(notes_before), 0)

        # Test finding no notes after a future date (relative to test execution)
        # This requires a bit of care if tests run across midnight, etc.
        from datetime import datetime, timedelta
        future_date = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d %H:%M:%S")
        notes_after = find_notes(date_range=(future_date, None))
        self.assertEqual(len(notes_after), 0)

    def test_update_note_content(self):
        initial_content = "Initial content before update."
        note_id = create_note(content=initial_content, tags_list=["original"])
        self.assertIsNotNone(note_id)

        updated_content = "Content has been successfully updated."
        new_version_id = update_note(original_note_id_to_update=note_id, new_content=updated_content)
        self.assertIsNotNone(new_version_id)
        self.assertNotEqual(new_version_id, note_id)

        # Verify old version
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT content, is_latest_version FROM notes WHERE note_id = ?", (note_id,))
        old_version_row = cursor.fetchone()
        self.assertEqual(old_version_row['content'], initial_content)
        self.assertEqual(old_version_row['is_latest_version'], 0)

        # Verify new version
        cursor.execute("SELECT content, is_latest_version, original_note_id FROM notes WHERE note_id = ?", (new_version_id,))
        new_version_row = cursor.fetchone()
        self.assertEqual(new_version_row['content'], updated_content)
        self.assertEqual(new_version_row['is_latest_version'], 1)
        self.assertEqual(new_version_row['original_note_id'], note_id)
        conn.close()

        # Verify find_notes returns the new version
        found_notes = find_notes(tags=["original"]) # Assuming tags are carried over
        self.assertEqual(len(found_notes), 1)
        self.assertEqual(found_notes[0]['note_id'], new_version_id)
        self.assertEqual(found_notes[0]['content'], updated_content)

    def test_update_note_tags(self):
        note_id = create_note(content="Note for tag update.", tags_list=["old_tag"])
        self.assertIsNotNone(note_id)

        new_tags = ["new_tag1", "new_tag2"]
        new_version_id = update_note(original_note_id_to_update=note_id, new_tags_list=new_tags)
        self.assertIsNotNone(new_version_id)

        # Verify new version tags
        found_notes = find_notes(tags=["new_tag1"])
        self.assertEqual(len(found_notes), 1)
        self.assertEqual(found_notes[0]['note_id'], new_version_id)
        self.assertEqual(sorted(found_notes[0]['tags']), sorted(new_tags))

        # Verify old tags are not on the new version if completely replaced
        found_by_old_tag = find_notes(tags=["old_tag"])
        self.assertEqual(len(found_by_old_tag), 0, "Old tag should not find the latest version if tags were replaced.")

    def test_update_note_properties(self):
        initial_props = {"status": "draft"}
        note_id = create_note(content="Note for prop update.", properties_dict=initial_props)
        self.assertIsNotNone(note_id)

        new_props = {"status": "published", "reviewed": True}
        new_version_id = update_note(original_note_id_to_update=note_id, new_properties_dict=new_props)
        self.assertIsNotNone(new_version_id)

        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT properties_json FROM notes WHERE note_id = ?", (new_version_id,))
        new_version_row = cursor.fetchone()
        conn.close()
        self.assertIsNotNone(new_version_row['properties_json'])
        self.assertEqual(json.loads(new_version_row['properties_json']), new_props)

    def test_update_note_all_fields(self):
        note_id = create_note(content="Initial content.", tags_list=["v1"], properties_dict={"ver": 1})
        self.assertIsNotNone(note_id)

        updated_content = "Updated content for all fields test."
        updated_tags = ["v2", "final"]
        updated_props = {"ver": 2, "complete": True}

        new_version_id = update_note(
            original_note_id_to_update=note_id, 
            new_content=updated_content,
            new_tags_list=updated_tags,
            new_properties_dict=updated_props
        )
        self.assertIsNotNone(new_version_id)

        found_notes = find_notes(tags=["v2", "final"])
        self.assertEqual(len(found_notes), 1)
        updated_note = found_notes[0]
        self.assertEqual(updated_note['note_id'], new_version_id)
        self.assertEqual(updated_note['content'], updated_content)
        self.assertEqual(sorted(updated_note['tags']), sorted(updated_tags))
        self.assertEqual(updated_note['properties'], updated_props)

        # Check that the old version is no longer the latest
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT is_latest_version FROM notes WHERE note_id = ?", (note_id,))
        old_version_status = cursor.fetchone()['is_latest_version']
        conn.close()
        self.assertEqual(old_version_status, 0)

    def test_update_non_existent_note(self):
        new_version_id = update_note(original_note_id_to_update=99999, new_content="test")
        self.assertIsNone(new_version_id, "Updating a non-existent note should fail and return None.")

    def test_update_carries_over_unspecified_fields(self):
        initial_content = "Content to be carried over."
        initial_tags = ["carry_tag"]
        initial_props = {"carry_prop": "value"}
        note_id = create_note(content=initial_content, tags_list=initial_tags, properties_dict=initial_props)
        self.assertIsNotNone(note_id)

        # Update only content
        updated_content_only = "Slightly new content."
        new_version_id = update_note(original_note_id_to_update=note_id, new_content=updated_content_only)
        self.assertIsNotNone(new_version_id)

        found_notes = find_notes(tags=initial_tags) # Search by original tag
        self.assertEqual(len(found_notes), 1)
        updated_note = found_notes[0]
        self.assertEqual(updated_note['note_id'], new_version_id)
        self.assertEqual(updated_note['content'], updated_content_only)
        self.assertEqual(sorted(updated_note['tags']), sorted(initial_tags)) # Tags should be carried over
        self.assertEqual(updated_note['properties'], initial_props)     # Properties should be carried over

    def test_get_note_history(self):
        # 1. Create an initial note
        original_content = "Version 1 content"
        original_tags = ["v1tag"]
        original_props = {"version": 1}
        note_v1_id = create_note(content=original_content, tags_list=original_tags, properties_dict=original_props)
        self.assertIsNotNone(note_v1_id)
        original_note_id = note_v1_id # In our setup, the first note_id is the original_note_id

        # 2. Update it once (creates v2)
        content_v2 = "Version 2 content - updated"
        tags_v2 = ["v2tag", "updated"]
        props_v2 = {"version": 2, "status": "revised"}
        note_v2_id = update_note(original_note_id, new_content=content_v2, new_tags_list=tags_v2, new_properties_dict=props_v2)
        self.assertIsNotNone(note_v2_id)

        # 3. Update it again (creates v3)
        content_v3 = "Version 3 content - final update"
        tags_v3 = ["v3tag", "final"]
        props_v3 = {"version": 3, "status": "finalized"}
        note_v3_id = update_note(original_note_id, new_content=content_v3, new_tags_list=tags_v3, new_properties_dict=props_v3)
        self.assertIsNotNone(note_v3_id)

        # 4. Get the history
        history = get_note_history(original_note_id)
        self.assertEqual(len(history), 3, "Should retrieve all 3 versions.")

        # 5. Verify versions in order (oldest first)
        # Version 1 (note_v1_id)
        self.assertEqual(history[0]['note_id'], note_v1_id)
        self.assertEqual(history[0]['original_note_id'], original_note_id)
        self.assertEqual(history[0]['content'], original_content)
        self.assertEqual(sorted(history[0]['tags']), sorted(original_tags))
        self.assertEqual(history[0]['properties'], original_props)
        self.assertEqual(history[0]['is_latest_version'], 0)

        # Version 2 (note_v2_id)
        self.assertEqual(history[1]['note_id'], note_v2_id)
        self.assertEqual(history[1]['original_note_id'], original_note_id)
        self.assertEqual(history[1]['content'], content_v2)
        self.assertEqual(sorted(history[1]['tags']), sorted(tags_v2))
        self.assertEqual(history[1]['properties'], props_v2)
        self.assertEqual(history[1]['is_latest_version'], 0)

        # Version 3 (note_v3_id - should be the latest)
        self.assertEqual(history[2]['note_id'], note_v3_id)
        self.assertEqual(history[2]['original_note_id'], original_note_id)
        self.assertEqual(history[2]['content'], content_v3)
        self.assertEqual(sorted(history[2]['tags']), sorted(tags_v3))
        self.assertEqual(history[2]['properties'], props_v3)
        self.assertEqual(history[2]['is_latest_version'], 1)

    def test_get_note_history_non_existent(self):
        history = get_note_history(original_note_id=88888) # Assuming this ID does not exist
        self.assertEqual(len(history), 0, "Should return an empty list for a non-existent original_note_id.")

    # --- Tests for Soft Delete Functionality ---

    def test_soft_delete_note_and_find(self):
        note_id = create_note(content="Note to be soft deleted.")
        self.assertIsNotNone(note_id)

        delete_success = soft_delete_note(original_note_id=note_id)
        self.assertTrue(delete_success)

        # Verify it's not found by default find_notes
        found = find_notes(content_keywords=["Note to be soft deleted"])
        self.assertEqual(len(found), 0, "Soft-deleted note should not be found by default find_notes.")

        # Verify its state in the database
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT is_deleted, deleted_at FROM notes WHERE original_note_id = ? AND is_latest_version = 1", (note_id,))
        note_state = cursor.fetchone()
        conn.close()

        self.assertIsNotNone(note_state, "Note should still exist in DB.")
        self.assertEqual(note_state['is_deleted'], 1, "is_deleted flag should be 1.")
        self.assertIsNotNone(note_state['deleted_at'], "deleted_at timestamp should be set.")

    def test_restore_note(self):
        note_id = create_note(content="Note to be restored.")
        self.assertTrue(soft_delete_note(original_note_id=note_id))

        restore_success = restore_note(original_note_id=note_id)
        self.assertTrue(restore_success)

        # Verify it's found again by find_notes
        found = find_notes(content_keywords=["Note to be restored"])
        self.assertEqual(len(found), 1)
        self.assertEqual(found[0]['original_note_id'], note_id)

        # Verify its state
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT is_deleted, deleted_at FROM notes WHERE original_note_id = ? AND is_latest_version = 1", (note_id,))
        note_state = cursor.fetchone()
        conn.close()

        self.assertIsNotNone(note_state)
        self.assertEqual(note_state['is_deleted'], 0, "is_deleted flag should be 0 after restore.")
        self.assertIsNone(note_state['deleted_at'], "deleted_at timestamp should be NULL after restore.")

    def test_get_deleted_notes(self):
        note1_id = create_note(content="Active note 1")
        note2_id = create_note(content="Note to delete 1")
        note3_id = create_note(content="Note to delete 2")
        
        self.assertTrue(soft_delete_note(note2_id))
        self.assertTrue(soft_delete_note(note3_id))

        deleted_notes = get_deleted_notes()
        self.assertEqual(len(deleted_notes), 2)
        deleted_original_ids = {n['original_note_id'] for n in deleted_notes}
        self.assertIn(note2_id, deleted_original_ids)
        self.assertIn(note3_id, deleted_original_ids)
        self.assertNotIn(note1_id, deleted_original_ids)

    def test_purge_deleted_notes_all(self):
        note1_id = create_note(content="Initial version to be purged")
        note2_id = create_note(content="To remain active")
        
        # Create a version history for note1_id BEFORE soft deleting the latest
        update_note(note1_id, "Purged note version 2") 
        # Now, the latest version is "Purged note version 2"
        
        # Soft delete the latest version of note1_id
        self.assertTrue(soft_delete_note(note1_id)) 

        purged_count = purge_deleted_notes()
        self.assertEqual(purged_count, 1, "Should report 1 original note lineage purged.")

        # Verify note1 (and its versions) is completely gone
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM notes WHERE original_note_id = ?", (note1_id,))
        self.assertIsNone(cursor.fetchone(), "Purged note should not exist in notes table.")
        
        # Verify associated tags are gone (if any were added to note1_id versions)
        # Example: if note1_id had tags, those note_tags entries should be gone.
        # Purge_deleted_notes itself handles deleting from note_tags.
        # We can check if any note_tags entries remain for the versions of note1_id (there should be none).
        # This is implicitly tested if the notes themselves are gone and foreign keys worked or manual delete was effective.

        # Verify note2 still exists
        cursor.execute("SELECT * FROM notes WHERE original_note_id = ?", (note2_id,))
        self.assertIsNotNone(cursor.fetchone(), "Active note should still exist.")
        conn.close()

        self.assertEqual(len(get_deleted_notes()), 0, "No soft-deleted notes should remain after purge all.")

    def test_purge_deleted_notes_older_than_days(self):
        note_old_id = create_note(content="Old deleted note", tags_list=["old_purge"])
        note_recent_id = create_note(content="Recent deleted note", tags_list=["recent_purge"])
        note_active_id = create_note(content="Active note")

        self.assertTrue(soft_delete_note(note_old_id))
        self.assertTrue(soft_delete_note(note_recent_id))

        # Manually update deleted_at for note_old_id to be 8 days ago
        eight_days_ago = datetime.now(timezone.utc) - timedelta(days=8)
        conn = get_db_connection()
        cursor = conn.cursor()
        # Find the specific latest version note_id for the original_note_id
        cursor.execute("SELECT note_id FROM notes WHERE original_note_id = ? AND is_latest_version = 1", (note_old_id,))
        old_latest_version_id = cursor.fetchone()['note_id']
        cursor.execute("UPDATE notes SET deleted_at = ? WHERE note_id = ?", (eight_days_ago.strftime('%Y-%m-%d %H:%M:%S'), old_latest_version_id))
        conn.commit()
        conn.close()
        
        purged_count = purge_deleted_notes(older_than_days=7)
        self.assertEqual(purged_count, 1, "Should purge only the note older than 7 days.")

        # Verify note_old_id is purged
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM notes WHERE original_note_id = ?", (note_old_id,))
        self.assertIsNone(cursor.fetchone(), "Old deleted note should be purged.")
        
        # Verify note_recent_id is NOT purged and still in deleted_notes
        deleted_notes = get_deleted_notes()
        self.assertEqual(len(deleted_notes), 1)
        self.assertEqual(deleted_notes[0]['original_note_id'], note_recent_id)
        conn.close()

    # --- Tests for Export/Import Functionality ---

    def test_export_all_notes_structure_and_basic_content(self):
        """Test the structure and basic content of the exported data."""
        # 1. Create some data
        note1_id = create_note(content="Export Test Note 1", tags_list=["export", "test1"], properties_dict={"source": "test"})
        self.assertIsNotNone(note1_id)
        update_note(original_note_id_to_update=note1_id, new_content="Export Test Note 1 - v2") # Create a new version
        
        note2_id = create_note(content="Export Test Note 2, deleted", tags_list=["export", "deleted"], properties_dict={"status": "old"})
        self.assertIsNotNone(note2_id)
        soft_delete_note(original_note_id=note2_id)

        note3_id = create_note(content="Export Test Note 3, simple") # No tags, no props
        self.assertIsNotNone(note3_id)

        # 2. Call export_all_notes
        exported_data = export_all_notes()
        self.assertIsNotNone(exported_data, "Exported data should not be None")

        # 3. Validate top-level structure
        self.assertIn("export_metadata", exported_data)
        self.assertIn("tags", exported_data)
        self.assertIn("notes", exported_data)
        self.assertIn("note_tags_relations", exported_data)

        # 4. Validate metadata
        metadata = exported_data["export_metadata"]
        self.assertEqual(metadata["format_version"], "1.0.1")
        self.assertIn("export_timestamp_utc", metadata)
        try:
            datetime.fromisoformat(metadata["export_timestamp_utc"].replace('Z', '+00:00'))
        except ValueError:
            self.fail("Metadata export_timestamp_utc is not a valid ISO format string")

        # 5. Validate tags structure (simple check for now)
        # Expected tags: export, test1, deleted (unique and lowercased by DB)
        exported_tag_names = [t['tag_name'] for t in exported_data['tags']]
        self.assertIn("export", exported_tag_names)
        self.assertIn("test1", exported_tag_names)
        self.assertIn("deleted", exported_tag_names)
        self.assertEqual(len(exported_data['tags']), 3) # export, test1, deleted

        # 6. Validate notes structure (spot checks)
        self.assertEqual(len(exported_data['notes']), 4) # 2 versions of note1, 1 of note2, 1 of note3
        
        found_note1_v1 = None
        found_note1_v2 = None
        found_note2 = None
        found_note3 = None

        for n_dict in exported_data['notes']:
            self.assertIn('note_id', n_dict)
            self.assertIn('original_note_id', n_dict)
            self.assertIn('content', n_dict)
            self.assertIn('created_at', n_dict)
            self.assertIn('is_latest_version', n_dict)
            self.assertIn('properties_json', n_dict) # Will be None if no props
            self.assertIn('is_deleted', n_dict)
            self.assertIn('deleted_at', n_dict) # Will be None if not deleted
            try:
                datetime.fromisoformat(n_dict['created_at'].replace('Z', '+00:00'))
                if n_dict['deleted_at']:
                    datetime.fromisoformat(n_dict['deleted_at'].replace('Z', '+00:00'))
            except ValueError:
                self.fail(f"Note {n_dict['note_id']} has invalid ISO date format for created_at or deleted_at")

            # Identify specific notes for more detailed checks
            if n_dict['content'] == "Export Test Note 1":
                found_note1_v1 = n_dict
            elif n_dict['content'] == "Export Test Note 1 - v2":
                found_note1_v2 = n_dict
            elif n_dict['content'] == "Export Test Note 2, deleted":
                found_note2 = n_dict
            elif n_dict['content'] == "Export Test Note 3, simple":
                found_note3 = n_dict
        
        self.assertIsNotNone(found_note1_v1, "Note 1 Version 1 not found in export")
        self.assertIsNotNone(found_note1_v2, "Note 1 Version 2 not found in export")
        self.assertIsNotNone(found_note2, "Note 2 not found in export")
        self.assertIsNotNone(found_note3, "Note 3 not found in export")

        # Check specific attributes
        self.assertEqual(found_note1_v1['is_latest_version'], 0)
        self.assertEqual(found_note1_v2['is_latest_version'], 1)
        self.assertEqual(json.loads(found_note1_v1['properties_json']), {"source": "test"})
        
        self.assertEqual(found_note2['is_deleted'], 1)
        self.assertIsNotNone(found_note2['deleted_at'])
        self.assertEqual(json.loads(found_note2['properties_json']), {"status": "old"})

        self.assertIsNone(found_note3['properties_json'])
        self.assertEqual(found_note3['is_deleted'], 0)
        self.assertIsNone(found_note3['deleted_at'])

        # 7. Validate note_tags_relations structure (spot checks)
        # Note 1 (v1 - ID note1_id) should have tags 'export', 'test1'
        # Note 1 (v2 - its own ID) should have tags 'export', 'test1' (assuming update carries them)
        # Note 2 (ID note2_id) should have tags 'export', 'deleted'
        # Note 3 (ID note3_id) should have no tags.

        # Get tag_ids from the exported_data['tags'] list to map names to IDs
        tag_map = {t['tag_name']: t['tag_id'] for t in exported_data['tags']}

        relations = exported_data['note_tags_relations']
        # Note1 v1 relations
        v1_tags = {r['tag_id'] for r in relations if r['note_version_id'] == found_note1_v1['note_id']}
        self.assertIn(tag_map['export'], v1_tags)
        self.assertIn(tag_map['test1'], v1_tags)
        self.assertEqual(len(v1_tags), 2)

        # Note1 v2 relations
        v2_tags = {r['tag_id'] for r in relations if r['note_version_id'] == found_note1_v2['note_id']}
        self.assertIn(tag_map['export'], v2_tags)
        self.assertIn(tag_map['test1'], v2_tags)
        self.assertEqual(len(v2_tags), 2)

        # Note2 relations
        n2_tags = {r['tag_id'] for r in relations if r['note_version_id'] == found_note2['note_id']}
        self.assertIn(tag_map['export'], n2_tags)
        self.assertIn(tag_map['deleted'], n2_tags)
        self.assertEqual(len(n2_tags), 2)

        # Note3 should have no relations
        n3_tag_ids = [r['tag_id'] for r in relations if r['note_version_id'] == found_note3['note_id']]
        self.assertEqual(len(n3_tag_ids), 0)
        
    def test_export_all_notes_empty_db(self):
        """Test exporting from an entirely empty database."""
        exported_data = export_all_notes()
        self.assertIsNotNone(exported_data)
        metadata = exported_data["export_metadata"]
        self.assertEqual(metadata["format_version"], "1.0.1")
        self.assertIn("export_timestamp_utc", metadata)
        self.assertEqual(len(exported_data['tags']), 0)
        self.assertEqual(len(exported_data['notes']), 0)
        self.assertEqual(len(exported_data['note_tags_relations']), 0)

    def test_import_notes_from_json_data(self):
        # 1. Prepare data (can use the export logic or a crafted dictionary)
        # For a robust test, let's craft a specific scenario.
        note1_orig_id, note1_v1_id, note1_v2_id = 1001, 1002, 1003 # Arbitrary IDs for testing preservation
        note2_orig_id, note2_v1_id = 2001, 2002
        tag1_id, tag2_id, tag3_id = 501, 502, 503

        sample_export_data = {
            "export_metadata": {
                "format_version": "1.0.1",
                "timestamp_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
            },
            "tags": [
                {"tag_id": tag1_id, "tag_name": "imported"},
                {"tag_id": tag2_id, "tag_name": "data"},
                {"tag_id": tag3_id, "tag_name": "test_tag"}
            ],
            "notes": [
                {
                    "note_id": note1_v1_id, "original_note_id": note1_orig_id, "content": "Imported Note 1, Version 1",
                    "created_at": (datetime.now(timezone.utc) - timedelta(days=2)).isoformat().replace("+00:00", "Z"),
                    "is_latest_version": 0, "properties_json": json.dumps({"imported_by": "test_v1"}),
                    "is_deleted": 0, "deleted_at": None
                },
                {
                    "note_id": note1_v2_id, "original_note_id": note1_orig_id, "content": "Imported Note 1, Version 2 (latest)",
                    "created_at": (datetime.now(timezone.utc) - timedelta(days=1)).isoformat().replace("+00:00", "Z"),
                    "is_latest_version": 1, "properties_json": json.dumps({"imported_by": "test_v2"}),
                    "is_deleted": 0, "deleted_at": None
                },
                {
                    "note_id": note2_v1_id, "original_note_id": note2_orig_id, "content": "Imported Note 2, Deleted",
                    "created_at": (datetime.now(timezone.utc) - timedelta(days=3)).isoformat().replace("+00:00", "Z"),
                    "is_latest_version": 1, "properties_json": None,
                    "is_deleted": 1, "deleted_at": (datetime.now(timezone.utc) - timedelta(hours=5)).isoformat().replace("+00:00", "Z")
                }
            ],
            "note_tags_relations": [
                {"note_version_id": note1_v1_id, "tag_id": tag1_id},
                {"note_version_id": note1_v1_id, "tag_id": tag2_id},
                {"note_version_id": note1_v2_id, "tag_id": tag1_id},
                {"note_version_id": note1_v2_id, "tag_id": tag3_id},
                {"note_version_id": note2_v1_id, "tag_id": tag2_id}
            ]
        }

        # 2. Call import_notes_from_json_data
        # Ensure DB is clean (setUp does this, but good to be mindful)
        import_successful = import_notes_from_json_data(sample_export_data)
        self.assertTrue(import_successful, "Import should be successful")

        # 3. Validate data in the database
        conn = get_db_connection()
        cursor = conn.cursor()

        # Validate tags
        cursor.execute("SELECT tag_id, tag_name FROM tags ORDER BY tag_id")
        db_tags = cursor.fetchall()
        self.assertEqual(len(db_tags), 3)
        self.assertEqual(db_tags[0]['tag_id'], tag1_id)
        self.assertEqual(db_tags[0]['tag_name'], "imported")
        self.assertEqual(db_tags[1]['tag_id'], tag2_id)
        self.assertEqual(db_tags[1]['tag_name'], "data")
        self.assertEqual(db_tags[2]['tag_id'], tag3_id)
        self.assertEqual(db_tags[2]['tag_name'], "test_tag")
        
        # Validate notes
        cursor.execute("SELECT note_id, original_note_id, content, properties_json, is_latest_version, is_deleted, deleted_at FROM notes ORDER BY note_id")
        db_notes = cursor.fetchall()
        self.assertEqual(len(db_notes), 3)

        # Note 1, Version 1
        self.assertEqual(db_notes[0]['note_id'], note1_v1_id)
        self.assertEqual(db_notes[0]['original_note_id'], note1_orig_id)
        self.assertEqual(db_notes[0]['content'], "Imported Note 1, Version 1")
        self.assertEqual(json.loads(db_notes[0]['properties_json']), {"imported_by": "test_v1"})
        self.assertEqual(db_notes[0]['is_latest_version'], 0)
        self.assertEqual(db_notes[0]['is_deleted'], 0)
        self.assertIsNone(db_notes[0]['deleted_at'])

        # Note 1, Version 2
        self.assertEqual(db_notes[1]['note_id'], note1_v2_id)
        self.assertEqual(db_notes[1]['original_note_id'], note1_orig_id)
        self.assertEqual(db_notes[1]['content'], "Imported Note 1, Version 2 (latest)")
        self.assertEqual(json.loads(db_notes[1]['properties_json']), {"imported_by": "test_v2"})
        self.assertEqual(db_notes[1]['is_latest_version'], 1)
        self.assertEqual(db_notes[1]['is_deleted'], 0)
        self.assertIsNone(db_notes[1]['deleted_at'])
        
        # Note 2, Version 1 (deleted)
        self.assertEqual(db_notes[2]['note_id'], note2_v1_id)
        self.assertEqual(db_notes[2]['original_note_id'], note2_orig_id)
        self.assertEqual(db_notes[2]['content'], "Imported Note 2, Deleted")
        self.assertIsNone(db_notes[2]['properties_json'])
        self.assertEqual(db_notes[2]['is_latest_version'], 1)
        self.assertEqual(db_notes[2]['is_deleted'], 1)
        self.assertIsNotNone(db_notes[2]['deleted_at'])
        # We could also parse and compare the deleted_at timestamp if needed for precision

        # Validate note_tags_relations
        cursor.execute("SELECT note_version_id, tag_id FROM note_tags ORDER BY note_version_id, tag_id")
        db_relations = cursor.fetchall()
        self.assertEqual(len(db_relations), 5)
        expected_relations = sorted([
            (note1_v1_id, tag1_id),
            (note1_v1_id, tag2_id),
            (note1_v2_id, tag1_id),
            (note1_v2_id, tag3_id),
            (note2_v1_id, tag2_id)
        ])
        actual_relations = sorted([(r['note_version_id'], r['tag_id']) for r in db_relations])
        self.assertEqual(actual_relations, expected_relations)
        
        conn.close()

    def test_import_notes_invalid_format_version(self):
        invalid_data = {
            "export_metadata": {"format_version": "0.9.0", "timestamp_utc": "..."},
            "tags": [], "notes": [], "note_tags_relations": []
        }
        self.assertFalse(import_notes_from_json_data(invalid_data), "Import should fail for invalid format version")

    def test_import_notes_missing_keys(self):
        invalid_data = {
            "export_metadata": {"format_version": "1.0.0", "timestamp_utc": "..."},
            # Missing "tags", "notes", "note_tags_relations"
        }
        self.assertFalse(import_notes_from_json_data(invalid_data), "Import should fail for missing top-level keys")

    # --- Purge Tests ---
    def test_purge_deleted_notes_all(self):
        """Test purging all soft-deleted notes."""
        note1_id = create_note(content="To be deleted 1")
        note2_id = create_note(content="To be deleted 2")
        note3_id = create_note(content="To keep")
        self.assertIsNotNone(note1_id)
        self.assertIsNotNone(note2_id)
        self.assertIsNotNone(note3_id)

        soft_delete_note(note1_id)
        soft_delete_note(note2_id)

        # Verify they are soft-deleted
        deleted_notes_before_purge = get_deleted_notes()
        self.assertEqual(len(deleted_notes_before_purge), 2)

        purged_count = purge_deleted_notes() # No days limit
        self.assertEqual(purged_count, 2, "Should purge two original notes (and their versions)")

        # Verify they are gone
        deleted_notes_after_purge = get_deleted_notes()
        self.assertEqual(len(deleted_notes_after_purge), 0)

        # Verify the kept note is still there and not deleted
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT note_id, is_deleted FROM notes WHERE original_note_id = ?", (note3_id,))
        kept_note_row = cursor.fetchone()
        conn.close()
        self.assertIsNotNone(kept_note_row)
        self.assertEqual(kept_note_row['note_id'], note3_id) # original_note_id is self for first version
        self.assertEqual(kept_note_row['is_deleted'], 0)

        # Also check that find_notes only finds the kept note
        all_remaining_notes = find_notes()
        self.assertEqual(len(all_remaining_notes), 1)
        self.assertEqual(all_remaining_notes[0]['original_note_id'], note3_id)


    def test_purge_deleted_notes_older_than_days(self):
        """Test purging soft-deleted notes older than a specific number of days."""
        # Create notes and manually set their created_at and deleted_at for precise control
        conn = get_db_connection()
        cursor = conn.cursor()

        # Note 1: Deleted 10 days ago
        ts_created_1 = (datetime.now(timezone.utc) - timedelta(days=15)).isoformat()
        ts_deleted_1 = (datetime.now(timezone.utc) - timedelta(days=10)).isoformat()
        cursor.execute("INSERT INTO notes (original_note_id, content, created_at, is_latest_version, is_deleted, deleted_at) VALUES (?, ?, ?, ?, ?, ?)",
                       (101, "Deleted 10 days ago", ts_created_1, 1, 1, ts_deleted_1))
        note1_id = cursor.lastrowid 
        cursor.execute("UPDATE notes SET original_note_id = ? WHERE note_id = ?", (note1_id, note1_id)) # Set original_note_id to self

        # Note 2: Deleted 5 days ago
        ts_created_2 = (datetime.now(timezone.utc) - timedelta(days=8)).isoformat()
        ts_deleted_2 = (datetime.now(timezone.utc) - timedelta(days=5)).isoformat()
        cursor.execute("INSERT INTO notes (original_note_id, content, created_at, is_latest_version, is_deleted, deleted_at) VALUES (?, ?, ?, ?, ?, ?)",
                       (102, "Deleted 5 days ago", ts_created_2, 1, 1, ts_deleted_2))
        note2_id = cursor.lastrowid
        cursor.execute("UPDATE notes SET original_note_id = ? WHERE note_id = ?", (note2_id, note2_id))

        # Note 3: Deleted 2 days ago
        ts_created_3 = (datetime.now(timezone.utc) - timedelta(days=3)).isoformat()
        ts_deleted_3 = (datetime.now(timezone.utc) - timedelta(days=2)).isoformat()
        cursor.execute("INSERT INTO notes (original_note_id, content, created_at, is_latest_version, is_deleted, deleted_at) VALUES (?, ?, ?, ?, ?, ?)",
                       (103, "Deleted 2 days ago", ts_created_3, 1, 1, ts_deleted_3))
        note3_id = cursor.lastrowid
        cursor.execute("UPDATE notes SET original_note_id = ? WHERE note_id = ?", (note3_id, note3_id))
        
        # Note 4: Not deleted
        ts_created_4 = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
        cursor.execute("INSERT INTO notes (original_note_id, content, created_at, is_latest_version, is_deleted, deleted_at) VALUES (?, ?, ?, ?, ?, ?)",
                       (104, "Not deleted", ts_created_4, 1, 0, None))
        note4_id = cursor.lastrowid
        cursor.execute("UPDATE notes SET original_note_id = ? WHERE note_id = ?", (note4_id, note4_id))
        conn.commit()

        # Verify initial state: 3 soft-deleted notes
        self.assertEqual(len(get_deleted_notes()), 3)

        # Purge notes deleted more than 7 days ago (should purge Note 1)
        purged_count_7_days = purge_deleted_notes(older_than_days=7)
        self.assertEqual(purged_count_7_days, 1, "Should purge 1 note older than 7 days")
        
        remaining_deleted = get_deleted_notes()
        self.assertEqual(len(remaining_deleted), 2, "Two soft-deleted notes should remain")
        remaining_deleted_ids = {n['original_note_id'] for n in remaining_deleted}
        self.assertNotIn(note1_id, remaining_deleted_ids)
        self.assertIn(note2_id, remaining_deleted_ids)
        self.assertIn(note3_id, remaining_deleted_ids)

        # Purge notes deleted more than 3 days ago (should purge Note 2 from remaining)
        # Note 1 is already gone.
        purged_count_3_days = purge_deleted_notes(older_than_days=3)
        self.assertEqual(purged_count_3_days, 1, "Should purge 1 more note older than 3 days (Note 2)")

        remaining_deleted_after_3 = get_deleted_notes()
        self.assertEqual(len(remaining_deleted_after_3), 1, "One soft-deleted note should remain (Note 3)")
        self.assertEqual(remaining_deleted_after_3[0]['original_note_id'], note3_id)

        # Purge notes deleted more than 0 days ago (should purge the last one, Note 3)
        purged_count_0_days = purge_deleted_notes(older_than_days=0)
        self.assertEqual(purged_count_0_days, 1, "Should purge the last note older than 0 days")
        self.assertEqual(len(get_deleted_notes()), 0, "No soft-deleted notes should remain")
        
        # Check that the non-deleted note is still there
        all_notes = find_notes()
        self.assertEqual(len(all_notes), 1)
        self.assertEqual(all_notes[0]['original_note_id'], note4_id)
        conn.close()

    def test_purge_deleted_notes_no_match_days_limit(self):
        note_id = create_note(content="Deleted recently")
        soft_delete_note(note_id)
        # Manually update deleted_at to be very recent to ensure it's not older than 1 day
        conn = get_db_connection()
        cursor = conn.cursor()
        recent_time = datetime.now(timezone.utc).isoformat()
        cursor.execute("UPDATE notes SET deleted_at = ? WHERE original_note_id = ?", (recent_time, note_id))
        conn.commit()
        conn.close()

        purged_count = purge_deleted_notes(older_than_days=1) # Purge if older than 1 day
        self.assertEqual(purged_count, 0)
        self.assertEqual(len(get_deleted_notes()), 1)

    def test_purge_deleted_notes_empty_db_or_no_deleted(self):
        self.assertEqual(purge_deleted_notes(), 0, "Should purge 0 notes from empty DB")
        self.assertEqual(purge_deleted_notes(older_than_days=5), 0, "Should purge 0 notes from empty DB with days limit")
        
        create_note(content="Active note")
        self.assertEqual(purge_deleted_notes(), 0, "Should purge 0 notes when no notes are deleted")
        self.assertEqual(purge_deleted_notes(older_than_days=5), 0, "Should purge 0 notes with days limit when none are deleted")


    def test_export_old_schema_and_import(self):
        # Simulate an older DB state by creating a note without soft-delete columns existing in the function's mind
        # This test depends on export_all_notes correctly handling the fallback.
        # We can't easily "remove" columns from the DB for one test, so we rely on export's flexibility.
        
        # Step 1: Create data and get an export (this will be a "new" schema export if cols exist)
        note1 = create_note("Old schema export test", ["schema_test"])
        temp_exported_data = export_all_notes()
        self.assertIsNotNone(temp_exported_data)

        # Step 2: Manually craft an "old schema" version of this data
        # by removing is_deleted and deleted_at from notes if present,
        # and adjusting metadata.
        crafted_old_schema_export = {
            "export_metadata": {
                "format_version": "1.0.1", # Simulate older export format
                "export_timestamp_utc": datetime.now(timezone.utc).isoformat()
            },
            "tags": [{"tag_id": t["tag_id"], "tag_name": t["tag_name"]} for t in temp_exported_data["tags"]],
            "notes": [],
            "note_tags_relations": [{"note_version_id": nt["note_version_id"], "tag_id": nt["tag_id"]} for nt in temp_exported_data["note_tags_relations"]]
        }
        for note_data in temp_exported_data["notes"]:
            old_note_entry = {
                "note_id": note_data["note_id"],
                "original_note_id": note_data["original_note_id"],
                "content": note_data["content"],
                "created_at": note_data["created_at"],
                "is_latest_version": note_data["is_latest_version"],
                "properties_json": note_data.get("properties_json")
                # Explicitly omit is_deleted, deleted_at
            }
            crafted_old_schema_export["notes"].append(old_note_entry)

        # Step 3: Clean DB and import this crafted "old schema" data
        self.setUp()
        import_success = import_notes_from_json_data(crafted_old_schema_export)
        self.assertTrue(import_success, "Import of crafted old schema data failed.")

        # Step 4: Verify the imported note defaults to not deleted
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT content, is_deleted, deleted_at FROM notes WHERE original_note_id = ?", (note1,))
        imported_note = cursor.fetchone()
        conn.close()
        
        self.assertIsNotNone(imported_note)
        self.assertEqual(imported_note["content"], "Old schema export test")
        self.assertEqual(imported_note["is_deleted"], 0, "Imported old-schema note should default to not deleted.")
        self.assertIsNone(imported_note["deleted_at"], "Imported old-schema note should have NULL deleted_at.")

    # --- Tests for Add/Remove Tag Functionality ---

    def test_add_tag_to_note(self):
        initial_content = "Content for add tag test"
        initial_tags = ["base_tag", "another_tag"]
        initial_props = {"status": "initial"}
        note_id = create_note(content=initial_content, tags_list=initial_tags, properties_dict=initial_props)
        self.assertIsNotNone(note_id)

        tag_to_add = "newly_added_tag"
        new_version_id = add_tag_to_note(original_note_id=note_id, tag_to_add=tag_to_add)
        self.assertIsNotNone(new_version_id, "add_tag_to_note should return the new version ID.")
        self.assertNotEqual(new_version_id, note_id, "A new version should be created.")

        # Verify new version details
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT content, properties_json FROM notes WHERE note_id = ?", (new_version_id,))
        new_version_data = cursor.fetchone()
        cursor.execute("SELECT t.tag_name FROM tags t JOIN note_tags nt ON t.tag_id = nt.tag_id WHERE nt.note_version_id = ?", (new_version_id,))
        new_version_tags = sorted([row['tag_name'] for row in cursor.fetchall()])
        conn.close()

        self.assertEqual(new_version_data['content'], initial_content, "Content should be carried over.")
        self.assertEqual(json.loads(new_version_data['properties_json']), initial_props, "Properties should be carried over.")
        
        expected_tags = sorted(initial_tags + [tag_to_add])
        self.assertEqual(new_version_tags, expected_tags, "Tags should include the newly added tag.")

        # Verify old version is no longer latest
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT is_latest_version FROM notes WHERE note_id = ?", (note_id,))
        old_version_status = cursor.fetchone()['is_latest_version']
        conn.close()
        self.assertEqual(old_version_status, 0)

    def test_add_existing_tag_to_note(self):
        note_id = create_note(content="Test duplicate tag add", tags_list=["tag1", "tag2"])
        self.assertIsNotNone(note_id)

        new_version_id = add_tag_to_note(original_note_id=note_id, tag_to_add="tag1") # Add existing tag
        self.assertIsNotNone(new_version_id, "Should still create a new version even if tag exists.")
        self.assertNotEqual(new_version_id, note_id)

        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT t.tag_name FROM tags t JOIN note_tags nt ON t.tag_id = nt.tag_id WHERE nt.note_version_id = ?", (new_version_id,))
        new_version_tags = sorted([row['tag_name'] for row in cursor.fetchall()])
        conn.close()
        self.assertEqual(new_version_tags, sorted(["tag1", "tag2"]), "Tags should remain the same if existing tag is added.")

    def test_add_tag_to_non_existent_note(self):
        result = add_tag_to_note(original_note_id=99999, tag_to_add="sometag")
        self.assertIsNone(result, "Should return None when trying to add tag to non-existent note.")

    def test_add_tag_to_soft_deleted_note(self):
        note_id = create_note(content="Note to be soft deleted then tagged")
        self.assertIsNotNone(note_id)
        self.assertTrue(soft_delete_note(note_id))

        result = add_tag_to_note(original_note_id=note_id, tag_to_add="newtag")
        self.assertIsNone(result, "Should not be able to add tag to a soft-deleted note's latest version.")

    def test_remove_tag_from_note(self):
        initial_content = "Content for remove tag test"
        initial_tags = ["tag_to_keep", "tag_to_remove", "another_tag"]
        initial_props = {"status": "stable"}
        note_id = create_note(content=initial_content, tags_list=initial_tags, properties_dict=initial_props)
        self.assertIsNotNone(note_id)

        tag_to_remove = "tag_to_remove"
        new_version_id = remove_tag_from_note(original_note_id=note_id, tag_to_remove=tag_to_remove)
        self.assertIsNotNone(new_version_id, "remove_tag_from_note should return the new version ID.")
        self.assertNotEqual(new_version_id, note_id, "A new version should be created.")

        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT content, properties_json FROM notes WHERE note_id = ?", (new_version_id,))
        new_version_data = cursor.fetchone()
        cursor.execute("SELECT t.tag_name FROM tags t JOIN note_tags nt ON t.tag_id = nt.tag_id WHERE nt.note_version_id = ?", (new_version_id,))
        new_version_tags = sorted([row['tag_name'] for row in cursor.fetchall()])
        conn.close()

        self.assertEqual(new_version_data['content'], initial_content)
        self.assertEqual(json.loads(new_version_data['properties_json']), initial_props)
        
        expected_tags = sorted(["tag_to_keep", "another_tag"])
        self.assertEqual(new_version_tags, expected_tags, "Tag should be removed correctly.")
        
        # Verify old version is no longer latest
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT is_latest_version FROM notes WHERE note_id = ?", (note_id,))
        old_version_status = cursor.fetchone()['is_latest_version']
        conn.close()
        self.assertEqual(old_version_status, 0)


    def test_remove_last_tag_from_note(self):
        note_id = create_note(content="Note with one tag", tags_list=["only_tag"])
        self.assertIsNotNone(note_id)

        new_version_id = remove_tag_from_note(original_note_id=note_id, tag_to_remove="only_tag")
        self.assertIsNotNone(new_version_id)

        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT t.tag_name FROM tags t JOIN note_tags nt ON t.tag_id = nt.tag_id WHERE nt.note_version_id = ?", (new_version_id,))
        new_version_tags = [row['tag_name'] for row in cursor.fetchall()]
        conn.close()
        self.assertEqual(len(new_version_tags), 0, "Note should have no tags after removing the last one.")

    def test_remove_non_existent_tag_from_note(self):
        note_id = create_note(content="Note with tags", tags_list=["tagA", "tagB"])
        self.assertIsNotNone(note_id)

        # Attempt to remove a tag not on the note
        result = remove_tag_from_note(original_note_id=note_id, tag_to_remove="non_existent_tag")
        self.assertIsNone(result, "Should return None if tag to remove is not found on the note.")

        # Verify no new version was created and original tags are intact on the latest version
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT is_latest_version FROM notes WHERE original_note_id = ? ORDER BY created_at DESC LIMIT 1", (note_id,))
        latest_version_info = cursor.fetchone()
        self.assertTrue(latest_version_info['is_latest_version']==1, "Original note should still be the latest version")

        cursor.execute("SELECT t.tag_name FROM tags t JOIN note_tags nt ON t.tag_id = nt.tag_id WHERE nt.note_version_id = ?", (note_id,)) # Check original note_id
        current_tags = sorted([row['tag_name'] for row in cursor.fetchall()])
        conn.close()
        self.assertEqual(current_tags, sorted(["taga", "tagb"]), "Tags should be unchanged if non-existent tag removal is attempted.")


    def test_remove_tag_from_non_existent_note(self):
        result = remove_tag_from_note(original_note_id=99999, tag_to_remove="sometag")
        self.assertIsNone(result, "Should return None when trying to remove tag from non-existent note.")

    def test_remove_tag_from_soft_deleted_note(self):
        note_id = create_note(content="Note to be soft deleted then tag removed", tags_list=["keeper", "remover"])
        self.assertIsNotNone(note_id)
        self.assertTrue(soft_delete_note(note_id))

        result = remove_tag_from_note(original_note_id=note_id, tag_to_remove="remover")
        self.assertIsNone(result, "Should not be able to remove tag from a soft-deleted note's latest version.")

    # --- Tests for List All Tags Functionality ---

    def test_list_all_tags_empty(self):
        all_tags = list_all_tags()
        self.assertEqual(all_tags, [], "Should return an empty list when no tags exist.")

    def test_list_all_tags_with_various_tags(self):
        create_note(content="Note 1", tags_list=["Python", "testing"])
        create_note(content="Note 2", tags_list=["python", "  Database  ", "UniqueTag"]) # Test case-insensitivity and stripping
        create_note(content="Note 3", tags_list=["testing", "Alpha"]) 
        # create_note will lowercase and strip tags

        all_tags = list_all_tags()
        expected_tags = sorted(["alpha", "database", "python", "testing", "uniquetag"])
        self.assertEqual(all_tags, expected_tags, "Should return all unique tags, sorted alphabetically and lowercased.")

    def test_list_all_tags_after_updates_and_deletes(self):
        # Initial tags
        note1_id = create_note(content="N1", tags_list=["initial", "common"])
        note2_id = create_note(content="N2", tags_list=["another", "COMMON"]) # common should be a duplicate

        # Add a new tag via update_note (which should also add to tags table)
        update_note(note1_id, new_tags_list=["initial", "common", "updated_tag_n1"])
        
        # Add a new tag via add_tag_to_note
        add_tag_to_note(note2_id, "added_tag_n2")

        # Soft delete a note - its tags should still be listed if they were on other notes or remain
        # If 'another' was unique to note2, after soft delete, it should still be listed by list_all_tags.
        # list_all_tags queries the 'tags' table directly, not based on active notes.
        soft_delete_note(note2_id) 

        # Create a note with a tag that will be removed
        note3_id = create_note(content="N3", tags_list=["temp_tag", "persistent"])
        remove_tag_from_note(note3_id, "temp_tag") # temp_tag should still exist in tags table if not orphaned.
                                                 # The current logic doesn't delete orphaned tags from 'tags' table.
                                                 # So "temp_tag" should still be listed.

        all_tags = list_all_tags()
        expected_tags = sorted([
            "initial", "common", "updated_tag_n1", 
            "another", "added_tag_n2", 
            "temp_tag", "persistent"
        ])
        self.assertEqual(all_tags, expected_tags)
        
    def test_list_all_tags_idempotency(self):
        create_note(content="N1", tags_list=["TagA", "tagB"])
        tags1 = list_all_tags()
        tags2 = list_all_tags() # Call again
        self.assertEqual(tags1, tags2, "Calling list_all_tags multiple times should yield the same result.")


if __name__ == '__main__':
    unittest.main() 