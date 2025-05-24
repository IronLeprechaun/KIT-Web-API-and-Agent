import sqlite3
import json
import sys # Keep for other potential uses, but not for path manipulation here
import os  # Keep for other potential uses
from typing import Union, List, Dict, Tuple, Optional # Added typing imports
from datetime import datetime, timedelta, timezone # Added for timestamping, timedelta and timezone

# Use explicit relative import for modules within the same package (KITCore)
from ..database_manager import get_db_connection, _get_effective_db_path_and_dir # Import for debugging path
# config.py is in the project root, which should be handled by the execution environment's Python path
# If direct execution of this file is needed for testing, that script should set up sys.path

print("!!! NOTE_TOOL.PY MODULE IS BEING LOADED/IMPORTED !!!", file=sys.stderr)

def _parse_tag_string(tag_string: str) -> Tuple[str, str]:
    """Parses a tag string into (type, value). Defaults to type 'general' if no colon is present."""
    tag_string = tag_string.strip().lower()
    if ':' in tag_string:
        parts = tag_string.split(':', 1)
        tag_type = parts[0].strip()
        tag_value = parts[1].strip()
        if not tag_type: # Handle cases like ":value"
            tag_type = "general"
        if not tag_value: # Handle cases like "type:"
            return "general", tag_type 
    else:
        tag_type = "general"
        tag_value = tag_string
    return tag_type, tag_value

def create_note(content: str, tags_list: Optional[List[str]] = None, properties_dict: Optional[Dict[str, any]] = None) -> Optional[int]:
    print("!!! CREATE_NOTE FUNCTION WAS CALLED !!!", file=sys.stderr)
    """
    Creates a new note in the database with versioning.
    Returns the original_note_id of the newly created note, or None if creation failed.
    """
    if tags_list is None:
        tags_list = []
    
    conn = None
    db_path_for_debug: Optional[str] = None # Initialize with a default value

    try:
        db_path_for_debug, _ = _get_effective_db_path_and_dir() # Get path for debugging
        print(f"NOTE_TOOL_DEBUG: create_note using DB: {db_path_for_debug}", file=sys.stderr)

        conn = get_db_connection()
        if conn is None:
            print(f"Database connection not available in create_note (using {db_path_for_debug}).", file=sys.stderr)
            return None
        
        cursor = conn.cursor()

        props_json = json.dumps(properties_dict) if properties_dict else None

        cursor.execute(
            "INSERT INTO notes (content, is_latest_version, properties_json) VALUES (?, ?, ?)",
            (content, 1, props_json) 
        )
        new_note_id = cursor.lastrowid

        if not new_note_id:
            # This case might indicate a more severe issue than a typical sqlite3.Error if lastrowid is None after successful execute
            print("Failed to retrieve new_note_id after insert in create_note.", file=sys.stderr)
            if conn: conn.rollback() # Attempt rollback before raising or returning
            return None # Or raise a custom exception

        cursor.execute(
            "UPDATE notes SET original_note_id = ? WHERE note_id = ?",
            (new_note_id, new_note_id)
        )

        for tag_string in tags_list:
            tag_type, tag_value = _parse_tag_string(tag_string)
            if not tag_value: # Skip if the value part is empty after parsing
                continue
            
            # Insert with type and value, using the new schema
            cursor.execute("INSERT OR IGNORE INTO tags (tag_type, tag_value) VALUES (?, ?)", (tag_type, tag_value))
            cursor.execute("SELECT tag_id FROM tags WHERE tag_type = ? AND tag_value = ?", (tag_type, tag_value))
            tag_row = cursor.fetchone()
            if tag_row:
                tag_id = tag_row['tag_id']
                cursor.execute(
                    "INSERT INTO note_tags (note_version_id, tag_id) VALUES (?, ?)",
                    (new_note_id, tag_id)
                )
            else:
                print(f"Warning: Could not find or create tag_id for tag_type='{tag_type}', tag_value='{tag_value}' in create_note", file=sys.stderr)

        print(f"NOTE_TOOL_DEBUG: create_note PRE-COMMIT for new_note_id: {new_note_id} in DB: {db_path_for_debug}", file=sys.stderr)
        conn.commit()
        print(f"NOTE_TOOL_DEBUG: create_note POST-COMMIT for new_note_id: {new_note_id}", file=sys.stderr)
        return new_note_id # Return the original_note_id which is same as note_id for new notes

    except sqlite3.Error as e:
        print(f"DATABASE ERROR in create_note: {e} (Type: {type(e).__name__}) using DB: {db_path_for_debug}", file=sys.stderr)
        # Optionally log the full traceback for sqlite3 errors if not too verbose
        # import traceback
        # traceback.print_exc(file=sys.stderr)
        if conn:
            conn.rollback()
        return None
    except Exception as e: # Catch other potential errors like JSON issues if properties_dict is malformed
        print(f"UNEXPECTED ERROR in create_note: {e} (Type: {type(e).__name__}) using DB: {db_path_for_debug}", file=sys.stderr)
        if conn: # conn might be None if get_db_connection failed before sqlite3.Error
            conn.rollback()
        return None
    finally:
        if conn:
            conn.close()

def find_notes(content_keywords: Optional[List[str]] = None, 
               include_tags: Optional[List[str]] = None, # Renamed from 'tags' and matches new logic
               exclude_tags: Optional[List[str]] = None,
               any_of_tags: Optional[List[str]] = None,
               date_range: Optional[Tuple[Optional[str], Optional[str]]] = None,
               original_note_ids: Optional[List[int]] = None,
               specific_version_ids: Optional[List[int]] = None) -> List[Dict[str, any]]:
    # print("!!! FIND_NOTES FUNCTION WAS CALLED !!!", file=sys.stderr) # Temporarily commented out
    """
    Finds notes based on content keywords, various tag conditions, date range, specific original_note_ids,
    or specific version_ids.
    When searching by specific_version_ids, is_latest_version and is_deleted are NOT automatically filtered.
    Otherwise, only returns notes that are the latest version and not soft-deleted.
    Returns a list of note dictionaries.
    """
    conn = None
    notes_found: List[Dict[str, any]] = []
    db_path_for_debug: Optional[str] = None # Initialize with a default value
    
    try:
        db_path_for_debug, _ = _get_effective_db_path_and_dir() # Get path for debugging
        # if specific_version_ids: # Prioritize search by specific version IDs
        #     print(f"NOTE_TOOL_DEBUG: find_notes (ID search) for specific_version_ids: {specific_version_ids} using DB: {db_path_for_debug}", file=sys.stderr)
        # elif original_note_ids:
        #     print(f"NOTE_TOOL_DEBUG: find_notes (ID search) for original_ids: {original_note_ids} using DB: {db_path_for_debug}", file=sys.stderr)
        # else:
        #     print(f"NOTE_TOOL_DEBUG: find_notes (general search) using DB: {db_path_for_debug}", file=sys.stderr)

        conn = get_db_connection()
        if conn is None:
            print(f"Database connection not available in find_notes (using {db_path_for_debug}).", file=sys.stderr)
            return notes_found

        cursor = conn.cursor()

        params: List[any] = []
        joins = ""

        if specific_version_ids: # Prioritize search by specific version IDs
            placeholders = ', '.join('?' * len(specific_version_ids))
            query_base = "SELECT n.note_id, n.original_note_id, n.content, n.created_at, n.properties_json, n.is_latest_version, n.is_deleted, n.deleted_at FROM notes n"
            conditions = [f"n.note_id IN ({placeholders})"]
            params.extend(specific_version_ids)
        elif original_note_ids:
            # Diagnostic: Simplify query drastically if only original_note_ids are provided
            placeholders = ', '.join('?' * len(original_note_ids))
            # Ensure we select from notes table aliased as 'n'
            query_base = "SELECT n.note_id, n.original_note_id, n.content, n.created_at, n.properties_json, n.is_latest_version, n.is_deleted FROM notes n"
            # ALWAYS filter for latest and not deleted, even with original_note_ids
            conditions = [
                f"n.original_note_id IN ({placeholders})",
                "n.is_latest_version = 1",
                "n.is_deleted = 0"
            ]
            params.extend(original_note_ids)
        else:
            # Base query selects distinct notes that are latest and not deleted (original logic)
            query_base = "SELECT DISTINCT n.note_id, n.original_note_id, n.content, n.created_at, n.properties_json FROM notes n"
            conditions = ["n.is_latest_version = 1", "n.is_deleted = 0"]
            # Keyword search
            if content_keywords:
                for keyword in content_keywords:
                    keyword = keyword.strip()
                    if keyword:
                        conditions.append("n.content LIKE ?")
                        params.append(f"%{keyword}%")
            
            if date_range and len(date_range) == 2:
                start_date, end_date = date_range
                if start_date:
                    conditions.append("n.created_at >= ?")
                    params.append(start_date)
                if end_date:
                    conditions.append("n.created_at <= ?")
                    params.append(end_date)

            tag_join_counter = 0

            if include_tags:
                parsed_include_tags = [_parse_tag_string(tag) for tag in include_tags if tag.strip()]
                if parsed_include_tags:
                    for tag_type, tag_value in parsed_include_tags:
                        if not tag_value: continue
                        joins += f" JOIN note_tags nt_incl_{tag_join_counter} ON n.note_id = nt_incl_{tag_join_counter}.note_version_id JOIN tags t_incl_{tag_join_counter} ON nt_incl_{tag_join_counter}.tag_id = t_incl_{tag_join_counter}.tag_id "
                        conditions.append(f"(t_incl_{tag_join_counter}.tag_type = ? AND t_incl_{tag_join_counter}.tag_value = ?)")
                        params.extend([tag_type, tag_value])
                        tag_join_counter += 1
            
            if any_of_tags:
                parsed_any_tags = [_parse_tag_string(tag) for tag in any_of_tags if tag.strip()]
                if parsed_any_tags:
                    any_tag_conditions = []
                    # Each any_tag needs its own join to check its type and value
                    # The overall condition is that AT LEAST ONE of these joins/conditions is met
                    # This requires a more complex structure, typically using a subquery or ORing groups of joins
                    # For simplicity here, we'll try to construct OR conditions for the tag checks on a single join if possible,
                    # but this might mean the note has *at least one* of these tags.
                    
                    # Create a single join for "any_of_tags" and then use OR conditions on the tag values
                    joins += f" JOIN note_tags nt_any_{tag_join_counter} ON n.note_id = nt_any_{tag_join_counter}.note_version_id JOIN tags t_any_{tag_join_counter} ON nt_any_{tag_join_counter}.tag_id = t_any_{tag_join_counter}.tag_id "
                    any_tag_sub_conditions = []
                    for tag_type, tag_value in parsed_any_tags:
                        if not tag_value: continue
                        any_tag_sub_conditions.append(f"(t_any_{tag_join_counter}.tag_type = ? AND t_any_{tag_join_counter}.tag_value = ?)")
                        params.extend([tag_type, tag_value])
                    
                    if any_tag_sub_conditions:
                        conditions.append(f"({ ' OR '.join(any_tag_sub_conditions) })")
                    tag_join_counter += 1 # Increment if join was added


            if exclude_tags:
                parsed_exclude_tags = [_parse_tag_string(tag) for tag in exclude_tags if tag.strip()]
                if parsed_exclude_tags:
                    for i, (tag_type, tag_value) in enumerate(parsed_exclude_tags):
                        if not tag_value: continue
                        # Using NOT EXISTS for each excluded typed tag
                        conditions.append(f"NOT EXISTS (SELECT 1 FROM note_tags nt_ex JOIN tags t_ex ON nt_ex.tag_id = t_ex.tag_id WHERE nt_ex.note_version_id = n.note_id AND t_ex.tag_type = ? AND t_ex.tag_value = ?)")
                        params.extend([tag_type, tag_value])

        query = query_base + joins
        if conditions:
            query += " WHERE " + " AND ".join(conditions)
        if not original_note_ids: # Add sorting only for general searches
            query += " ORDER BY n.created_at DESC"
        elif original_note_ids and len(conditions) > 1: # If other conditions were somehow added with original_ids
             query += " ORDER BY n.created_at DESC"

        # print(f"NOTE_TOOL_DEBUG: find_notes EXECUTING QUERY: {query} with PARAMS: {params}", file=sys.stderr) # Temporarily commented out
        cursor.execute(query, params)
        rows = cursor.fetchall()
        # print(f"NOTE_TOOL_DEBUG: find_notes FOUND {len(rows)} rows.", file=sys.stderr) # Temporarily commented out

        notes_by_id: Dict[int, Dict[str, any]] = {}
        note_ids_for_tags_query: List[int] = []

        for row_data in rows:
            note_id = row_data['note_id']
            note: Dict[str, any] = dict(row_data)
            if note.get('properties_json'):
                try:
                    note['properties'] = json.loads(note['properties_json'])
                except json.JSONDecodeError as je:
                    print(f"JSON decode error for note_id {note_id}: {je}", file=sys.stderr)
                    note['properties'] = {}
            else:
                note['properties'] = {}
            note['tags'] = [] # Initialize with empty list
            notes_by_id[note_id] = note
            if note_id not in note_ids_for_tags_query: # Should always be true if rows are unique by note_id
                note_ids_for_tags_query.append(note_id)

        if note_ids_for_tags_query:
            tags_query_placeholders = ', '.join('?' * len(note_ids_for_tags_query))
            tag_cursor = conn.cursor()
            tag_cursor.execute(
                f"SELECT nt.note_version_id, t.tag_type, t.tag_value FROM tags t JOIN note_tags nt ON t.tag_id = nt.tag_id WHERE nt.note_version_id IN ({tags_query_placeholders})", 
                tuple(note_ids_for_tags_query)
            )
            all_note_tags_rows = tag_cursor.fetchall()
            
            for tag_row in all_note_tags_rows:
                note_id_for_tag = tag_row['note_version_id']
                ttype, tvalue = tag_row['tag_type'], tag_row['tag_value']
                formatted_tag = f"{ttype}:{tvalue}" if ttype != 'general' else tvalue
                if note_id_for_tag in notes_by_id:
                    notes_by_id[note_id_for_tag]['tags'].append(formatted_tag)
        
        notes_found = list(notes_by_id.values()) # Convert back to list of dicts

    except sqlite3.Error as e:
        print(f"DATABASE ERROR in find_notes: {e} (Type: {type(e).__name__}) using DB: {db_path_for_debug}", file=sys.stderr)
    except Exception as e:
        print(f"UNEXPECTED ERROR in find_notes: {e} (Type: {type(e).__name__}) using DB: {db_path_for_debug}", file=sys.stderr)
    finally:
        if conn:
            conn.close()
    return notes_found

def update_note(
    original_note_id_to_update: int, 
    new_content: Optional[str] = None, 
    new_tags_list: Optional[List[str]] = None, 
    new_properties_dict: Optional[Dict[str, any]] = None
) -> Optional[int]:
    """
    Updates an existing note by creating a new version.
    Returns the note_id of the new version, or None if update failed.
    """
    conn = None
    try:
        conn = get_db_connection()
        if conn is None:
            print(f"Database connection not available in update_note.", file=sys.stderr)
            return None

        cursor = conn.cursor()

        cursor.execute(
            "SELECT note_id, content, properties_json FROM notes WHERE original_note_id = ? AND is_latest_version = 1",
            (original_note_id_to_update,)
        )
        current_latest_note = cursor.fetchone()

        if not current_latest_note:
            print(f"No latest version found for original_note_id {original_note_id_to_update} in update_note.", file=sys.stderr)
            return None

        current_latest_note_id = current_latest_note['note_id']
        current_content = current_latest_note['content']
        current_properties_json = current_latest_note['properties_json']

        # Fetch current tags in the new format (type, value)
        cursor.execute(
            "SELECT t.tag_type, t.tag_value FROM tags t JOIN note_tags nt ON t.tag_id = nt.tag_id WHERE nt.note_version_id = ?",
            (current_latest_note_id,)
        )
        current_tags_tuples = {(row['tag_type'], row['tag_value']) for row in cursor.fetchall()} # Use a set for efficient add

        content_for_new_version = new_content if new_content is not None else current_content
        
        tags_for_new_version_tuples: List[Tuple[str, str]]
        if new_tags_list is not None:
            tags_for_new_version_tuples = [_parse_tag_string(tag) for tag in new_tags_list if tag.strip()]
            # Filter out any tags that became empty after parsing, especially the value part
            tags_for_new_version_tuples = [(ttype, tval) for ttype, tval in tags_for_new_version_tuples if tval]
        else:
            tags_for_new_version_tuples = current_tags_tuples
        
        # Handle properties update (merge with existing)
        current_properties = {}
        if current_properties_json:
            try:
                current_properties = json.loads(current_properties_json)
            except json.JSONDecodeError:
                print(f"Warning: Could not decode existing properties_json for note_id {current_latest_note_id}. Starting with empty properties.", file=sys.stderr)
                current_properties = {} # Default to empty if malformed

        if new_properties_dict is not None:
            if not isinstance(current_properties, dict): # Ensure current_properties is a dict before updating
                print(f"Warning: Existing properties for note_id {current_latest_note_id} was not a dict. Overwriting with new properties.", file=sys.stderr)
                current_properties = {}
            current_properties.update(new_properties_dict) # Merge new properties into existing
            properties_for_new_version_json = json.dumps(current_properties)
        elif current_properties_json is not None: # No new properties, keep current
            properties_for_new_version_json = current_properties_json
        else: # No current and no new, so empty
            properties_for_new_version_json = json.dumps({}) 

        # Start transaction explicitly if not already started by sqlite3 module on DML
        # cursor.execute("BEGIN TRANSACTION") # Or rely on commit/rollback

        cursor.execute(
            "UPDATE notes SET is_latest_version = 0 WHERE note_id = ?",
            (current_latest_note_id,)
        )

        cursor.execute(
            "INSERT INTO notes (original_note_id, content, is_latest_version, properties_json) VALUES (?, ?, ?, ?)",
            (original_note_id_to_update, content_for_new_version, 1, properties_for_new_version_json)
        )
        new_version_note_id = cursor.lastrowid

        if not new_version_note_id:
            print(f"Failed to create new version for note {original_note_id_to_update} in update_note.", file=sys.stderr)
            if conn: conn.rollback()
            return None

        # Add new tags for the new version
        # if tags_for_new_version_tuples is None: # This check is not strictly needed due to above logic but safe
        #     tags_for_new_version_tuples = [] 
        
        for tag_type, tag_value in tags_for_new_version_tuples:
            # Value already checked for emptiness above
            cursor.execute("INSERT OR IGNORE INTO tags (tag_type, tag_value) VALUES (?, ?)", (tag_type, tag_value))
            cursor.execute("SELECT tag_id FROM tags WHERE tag_type = ? AND tag_value = ?", (tag_type, tag_value))
            tag_row = cursor.fetchone()
            if tag_row:
                tag_id = tag_row['tag_id']
                cursor.execute(
                    "INSERT INTO note_tags (note_version_id, tag_id) VALUES (?, ?)",
                    (new_version_note_id, tag_id)
                )
            else:
                print(f"Warning: Could not find or create tag_id for tag_type='{tag_type}', tag_value='{tag_value}' in update_note", file=sys.stderr)

        conn.commit()
        return new_version_note_id

    except sqlite3.Error as e:
        print(f"Database error in update_note: {e}", file=sys.stderr)
        if conn:
            conn.rollback()
        return None
    except Exception as e:
        print(f"Unexpected error in update_note: {e}", file=sys.stderr)
        if conn:
            conn.rollback()
        return None
    finally:
        if conn:
            conn.close()

def add_tag_to_note(original_note_id: int, tag_to_add: str) -> Optional[int]:
    """
    Adds a single tag to an existing note by creating a new version.
    The new tag is added to the existing set of tags.
    Returns the note_id of the new version, or None if update failed.
    """
    conn = None
    try:
        conn = get_db_connection()
        if conn is None:
            print(f"Database connection not available in add_tag_to_note.", file=sys.stderr)
            return None

        cursor = conn.cursor()

        # Get current latest version details
        cursor.execute(
            "SELECT note_id, content, properties_json FROM notes WHERE original_note_id = ? AND is_latest_version = 1 AND is_deleted = 0",
            (original_note_id,)
        )
        current_latest_note = cursor.fetchone()

        if not current_latest_note:
            print(f"No active latest version found for original_note_id {original_note_id} in add_tag_to_note.", file=sys.stderr)
            return None

        current_latest_note_id = current_latest_note['note_id']
        current_content = current_latest_note['content']
        current_properties_json = current_latest_note['properties_json']

        # Get current tags as (type, value) tuples
        cursor.execute(
            "SELECT t.tag_type, t.tag_value FROM tags t JOIN note_tags nt ON t.tag_id = nt.tag_id WHERE nt.note_version_id = ?",
            (current_latest_note_id,)
        )
        current_tags_tuples = {(row['tag_type'], row['tag_value']) for row in cursor.fetchall()} # Use a set for efficient add

        # Parse the new tag to add
        tag_type_to_add, tag_value_to_add = _parse_tag_string(tag_to_add)
        if not tag_value_to_add: # If the value part is empty after parsing
            print(f"Tag to add (value part) cannot be empty: '{tag_to_add}'", file=sys.stderr)
            return None 
        
        new_tag_tuple = (tag_type_to_add, tag_value_to_add)
        
        updated_tags_tuples_set = current_tags_tuples.copy()
        updated_tags_tuples_set.add(new_tag_tuple)
        tags_for_new_version_tuples = list(updated_tags_tuples_set)

        # Set old version to not be latest
        cursor.execute(
            "UPDATE notes SET is_latest_version = 0 WHERE note_id = ?",
            (current_latest_note_id,)
        )

        # Insert new version
        cursor.execute(
            "INSERT INTO notes (original_note_id, content, is_latest_version, properties_json) VALUES (?, ?, ?, ?)",
            (original_note_id, current_content, 1, current_properties_json)
        )
        new_version_note_id = cursor.lastrowid

        if not new_version_note_id:
            print(f"Failed to create new version for note {original_note_id} in add_tag_to_note.", file=sys.stderr)
            if conn: conn.rollback()
            return None

        # Add all tags (current + new) to the new version
        for tag_type, tag_value in tags_for_new_version_tuples:
            # Tag type/value are already parsed and validated for emptiness (value part)
            cursor.execute("INSERT OR IGNORE INTO tags (tag_type, tag_value) VALUES (?, ?)", (tag_type, tag_value))
            cursor.execute("SELECT tag_id FROM tags WHERE tag_type = ? AND tag_value = ?", (tag_type, tag_value))
            tag_row = cursor.fetchone()
            if tag_row:
                tag_id = tag_row['tag_id']
                cursor.execute(
                    "INSERT INTO note_tags (note_version_id, tag_id) VALUES (?, ?)",
                    (new_version_note_id, tag_id)
                )
            else:
                # This should ideally not happen if INSERT OR IGNORE worked
                print(f"Warning: Could not find or create tag_id for tag_type='{tag_type}', tag_value='{tag_value}' in add_tag_to_note", file=sys.stderr)

        conn.commit()
        return new_version_note_id

    except sqlite3.Error as e:
        print(f"Database error in add_tag_to_note: {e}", file=sys.stderr)
        if conn: conn.rollback()
        return None
    except Exception as e:
        print(f"Unexpected error in add_tag_to_note: {e}", file=sys.stderr)
        if conn: conn.rollback()
        return None
    finally:
        if conn: conn.close()

def remove_tag_from_note(original_note_id: int, tag_to_remove: str) -> Optional[int]:
    """
    Removes a single tag from an existing note by creating a new version.
    The specified tag is removed from the existing set of tags.
    Returns the note_id of the new version, or None if update failed or tag not found.
    """
    conn = None
    try:
        conn = get_db_connection()
        if conn is None:
            print(f"Database connection not available in remove_tag_from_note.", file=sys.stderr)
            return None

        cursor = conn.cursor()

        # Get current latest version details
        cursor.execute(
            "SELECT note_id, content, properties_json FROM notes WHERE original_note_id = ? AND is_latest_version = 1 AND is_deleted = 0",
            (original_note_id,)
        )
        current_latest_note = cursor.fetchone()

        if not current_latest_note:
            print(f"No active latest version found for original_note_id {original_note_id} in remove_tag_from_note.", file=sys.stderr)
            return None

        current_latest_note_id = current_latest_note['note_id']
        current_content = current_latest_note['content']
        current_properties_json = current_latest_note['properties_json']

        # Get current tags as (type, value) tuples
        cursor.execute(
            "SELECT t.tag_type, t.tag_value FROM tags t JOIN note_tags nt ON t.tag_id = nt.tag_id WHERE nt.note_version_id = ?",
            (current_latest_note_id,)
        )
        current_tags_tuples_set = {(row['tag_type'], row['tag_value']) for row in cursor.fetchall()} # Use a set for efficient removal

        # Parse the tag to remove
        tag_type_to_remove, tag_value_to_remove = _parse_tag_string(tag_to_remove)
        if not tag_value_to_remove:
            print(f"Tag to remove (value part) cannot be empty: '{tag_to_remove}'", file=sys.stderr)
            return None

        tag_tuple_to_remove = (tag_type_to_remove, tag_value_to_remove)

        if tag_tuple_to_remove not in current_tags_tuples_set:
            print(f"Tag '{tag_type_to_remove}:{tag_value_to_remove}' not found on note {original_note_id}. No changes made.", file=sys.stderr)
            return None 

        updated_tags_tuples_set = current_tags_tuples_set.copy()
        updated_tags_tuples_set.discard(tag_tuple_to_remove) 
        tags_for_new_version_tuples = list(updated_tags_tuples_set)

        # Set old version to not be latest
        cursor.execute(
            "UPDATE notes SET is_latest_version = 0 WHERE note_id = ?",
            (current_latest_note_id,)
        )

        # Insert new version
        cursor.execute(
            "INSERT INTO notes (original_note_id, content, is_latest_version, properties_json) VALUES (?, ?, ?, ?)",
            (original_note_id, current_content, 1, current_properties_json)
        )
        new_version_note_id = cursor.lastrowid

        if not new_version_note_id:
            print(f"Failed to create new version for note {original_note_id} in remove_tag_from_note.", file=sys.stderr)
            if conn: conn.rollback()
            return None

        # Add remaining tags to the new version
        for tag_type, tag_value in tags_for_new_version_tuples:
            # Tag type/value are already parsed
            cursor.execute("INSERT OR IGNORE INTO tags (tag_type, tag_value) VALUES (?, ?)", (tag_type, tag_value))
            cursor.execute("SELECT tag_id FROM tags WHERE tag_type = ? AND tag_value = ?", (tag_type, tag_value))
            tag_row = cursor.fetchone()
            if tag_row:
                tag_id = tag_row['tag_id']
                cursor.execute(
                    "INSERT INTO note_tags (note_version_id, tag_id) VALUES (?, ?)",
                    (new_version_note_id, tag_id)
                )
            else:
                print(f"Warning: Could not find or create tag_id for tag_type='{tag_type}', tag_value='{tag_value}' in remove_tag_from_note", file=sys.stderr)

        conn.commit()
        return new_version_note_id

    except sqlite3.Error as e:
        print(f"Database error in remove_tag_from_note: {e}", file=sys.stderr)
        if conn: conn.rollback()
        return None
    except Exception as e:
        print(f"Unexpected error in remove_tag_from_note: {e}", file=sys.stderr)
        if conn: conn.rollback()
        return None
    finally:
        if conn: conn.close()

def get_note_history(original_note_id: int) -> List[Dict[str, any]]:
    """
    Retrieves all versions of a note, ordered from newest to oldest.
    Returns a list of note dictionaries.
    """
    conn = None
    history: List[Dict[str, any]] = []
    try:
        conn = get_db_connection()
        if conn is None:
            print(f"Database connection not available in get_note_history.", file=sys.stderr)
            return history # Return empty list

        cursor = conn.cursor()
        cursor.execute(
            "SELECT note_id, original_note_id, content, created_at, is_latest_version, properties_json "
            "FROM notes WHERE original_note_id = ? ORDER BY created_at DESC",
            (original_note_id,)
        )
        rows = cursor.fetchall()

        for row_data in rows:
            note_version: Dict[str, any] = dict(row_data)
            if note_version.get('properties_json'):
                try:
                    note_version['properties'] = json.loads(note_version['properties_json'])
                except json.JSONDecodeError as je:
                    print(f"JSON decode error for note_id {note_version.get('note_id')} in history: {je}", file=sys.stderr)
                    note_version['properties'] = {}
            else:
                note_version['properties'] = {}
            
            tag_cursor = conn.cursor() # New cursor for this operation
            tag_cursor.execute(
                "SELECT t.tag_type, t.tag_value FROM tags t JOIN note_tags nt ON t.tag_id = nt.tag_id WHERE nt.note_version_id = ?",
                (note_version['note_id'],)
            )
            tag_rows = tag_cursor.fetchall()
            formatted_tags = []
            for tag_row in tag_rows:
                ttype, tvalue = tag_row['tag_type'], tag_row['tag_value']
                if ttype == 'general':
                    formatted_tags.append(tvalue)
                else:
                    formatted_tags.append(f"{ttype}:{tvalue}")
            note_version['tags'] = formatted_tags
            history.append(note_version)

    except sqlite3.Error as e:
        print(f"Database error in get_note_history: {e}", file=sys.stderr)
    except Exception as e:
        print(f"Unexpected error in get_note_history: {e}", file=sys.stderr)
    finally:
        if conn:
            conn.close()
    return history

def soft_delete_note(original_note_id: int) -> bool:
    """
    Soft deletes the latest version of a note.
    Sets is_deleted to 1 and records the deleted_at timestamp.
    Returns True on success, False on failure.
    """
    conn = None
    try:
        conn = get_db_connection()
        if conn is None:
            print(f"Database connection not available in soft_delete_note.", file=sys.stderr)
            return False
        
        cursor = conn.cursor()
        
        # Find the current latest version of the note that is not already deleted
        cursor.execute(
            "SELECT note_id FROM notes WHERE original_note_id = ? AND is_latest_version = 1 AND is_deleted = 0",
            (original_note_id,)
        )
        note_to_delete = cursor.fetchone()

        if not note_to_delete:
            print(f"No active (non-deleted, latest) version found for original_note_id {original_note_id} to soft delete.", file=sys.stderr)
            return False

        note_id_to_delete = note_to_delete['note_id']
        
        cursor.execute(
            "UPDATE notes SET is_deleted = 1, deleted_at = ? WHERE note_id = ?",
            (datetime.now(), note_id_to_delete)
        )
        
        conn.commit()
        return cursor.rowcount > 0 # Returns True if a row was updated

    except sqlite3.Error as e:
        print(f"Database error in soft_delete_note for original_note_id {original_note_id}: {e}", file=sys.stderr)
        if conn:
            conn.rollback()
        return False
    except Exception as e:
        print(f"Unexpected error in soft_delete_note for original_note_id {original_note_id}: {e}", file=sys.stderr)
        if conn:
            conn.rollback()
        return False
    finally:
        if conn:
            conn.close()

def restore_note(original_note_id: int) -> bool:
    """
    Restores a soft-deleted note (latest version).
    Sets is_deleted to 0 and clears the deleted_at timestamp.
    Returns True on success, False on failure.
    """
    conn = None
    try:
        conn = get_db_connection()
        if conn is None:
            print(f"Database connection not available in restore_note.", file=sys.stderr)
            return False
        
        cursor = conn.cursor()

        # Find the latest version of the note that is currently soft-deleted
        cursor.execute(
            "SELECT note_id FROM notes WHERE original_note_id = ? AND is_latest_version = 1 AND is_deleted = 1",
            (original_note_id,)
        )
        note_to_restore = cursor.fetchone()

        if not note_to_restore:
            print(f"No soft-deleted latest version found for original_note_id {original_note_id} to restore.", file=sys.stderr)
            return False
        
        note_id_to_restore = note_to_restore['note_id']

        cursor.execute(
            "UPDATE notes SET is_deleted = 0, deleted_at = NULL WHERE note_id = ?",
            (note_id_to_restore,)
        )
        
        conn.commit()
        return cursor.rowcount > 0 # Returns True if a row was updated

    except sqlite3.Error as e:
        print(f"Database error in restore_note for original_note_id {original_note_id}: {e}", file=sys.stderr)
        if conn:
            conn.rollback()
        return False
    except Exception as e:
        print(f"Unexpected error in restore_note for original_note_id {original_note_id}: {e}", file=sys.stderr)
        if conn:
            conn.rollback()
        return False
    finally:
        if conn:
            conn.close()

def get_deleted_notes() -> List[Dict[str, any]]:
    """
    Retrieves all notes that are marked as soft-deleted and are the latest version.
    Returns a list of note dictionaries, including deleted_at.
    """
    conn = None
    deleted_notes_found: List[Dict[str, any]] = []
    try:
        conn = get_db_connection()
        if conn is None:
            print(f"Database connection not available in get_deleted_notes.", file=sys.stderr)
            return deleted_notes_found
            
        cursor = conn.cursor()

        query = """
            SELECT DISTINCT n.note_id, n.original_note_id, n.content, n.created_at, 
                           n.properties_json, n.deleted_at 
            FROM notes n
            WHERE n.is_latest_version = 1 AND n.is_deleted = 1
            ORDER BY n.deleted_at DESC
        """
        
        cursor.execute(query)
        rows = cursor.fetchall()

        for row_data in rows:
            note: Dict[str, any] = dict(row_data)
            if note.get('properties_json'):
                try:
                    note['properties'] = json.loads(note['properties_json'])
                except json.JSONDecodeError as je:
                    print(f"JSON decode error for note_id {note.get('note_id')} in get_deleted_notes: {je}", file=sys.stderr)
                    note['properties'] = {}
            else:
                note['properties'] = {}
            
            tag_cursor = conn.cursor()
            tag_cursor.execute(
                "SELECT t.tag_type, t.tag_value FROM tags t JOIN note_tags nt ON t.tag_id = nt.tag_id WHERE nt.note_version_id = ?", 
                (note['note_id'],)
            )
            note_tags_rows = tag_cursor.fetchall()
            formatted_tags = []
            for tag_row in note_tags_rows:
                ttype, tvalue = tag_row['tag_type'], tag_row['tag_value']
                if ttype == 'general':
                    formatted_tags.append(tvalue)
                else:
                    formatted_tags.append(f"{ttype}:{tvalue}")
            note['tags'] = formatted_tags
            deleted_notes_found.append(note)

    except sqlite3.Error as e:
        print(f"Database error in get_deleted_notes: {e}", file=sys.stderr)
    except Exception as e:
        print(f"Unexpected error in get_deleted_notes: {e}", file=sys.stderr)
    finally:
        if conn:
            conn.close()
    return deleted_notes_found

def purge_deleted_notes(older_than_days: Optional[int] = None) -> int:
    """
    Permanently deletes notes that have been soft-deleted.
    If older_than_days is specified, only notes soft-deleted longer than that period are purged.
    When a note (original_note_id) is purged, ALL its versions are deleted.
    Returns the number of original notes (lineages) purged.
    """
    conn = None
    purged_original_notes_count = 0
    try:
        conn = get_db_connection()
        if conn is None:
            print("Database connection not available in purge_deleted_notes.", file=sys.stderr)
            return 0
        
        cursor = conn.cursor()

        # First, identify the original_note_ids of notes whose latest version is soft-deleted
        # and meets the older_than_days criteria.
        query_select_deletable = """
            SELECT DISTINCT original_note_id 
            FROM notes
            WHERE is_latest_version = 1 AND is_deleted = 1
        """
        params_select: List[any] = []

        if older_than_days is not None:
            purge_before_date = datetime.now() - timedelta(days=older_than_days)
            query_select_deletable += " AND deleted_at < ?"
            params_select.append(purge_before_date)
        
        cursor.execute(query_select_deletable, params_select)
        original_ids_to_purge = [row['original_note_id'] for row in cursor.fetchall()]

        if not original_ids_to_purge:
            # print("No notes found meeting purge criteria.", file=sys.stdout) # Or use logger
            return 0

        # For each original_note_id, delete all its versions and associated tags
        # It's crucial to handle foreign key constraints if ON DELETE CASCADE is not set up
        # or to delete from child tables first.
        # SQLite by default does not enforce foreign keys unless PRAGMA foreign_keys = ON;
        # Assuming we need to manually delete from note_tags.

        for original_id in original_ids_to_purge:
            if original_id is None: # Should not happen if data is consistent
                continue

            # Get all note_ids (versions) for this original_id
            cursor.execute("SELECT note_id FROM notes WHERE original_note_id = ?", (original_id,))
            note_versions_to_delete = [row['note_id'] for row in cursor.fetchall()]

            if not note_versions_to_delete:
                continue

            # Delete from note_tags for all these versions
            # Using a placeholder for a list of IDs
            placeholders = ','.join('?' for _ in note_versions_to_delete)
            cursor.execute(f"DELETE FROM note_tags WHERE note_version_id IN ({placeholders})", note_versions_to_delete)
            
            # Delete all versions from notes table
            cursor.execute("DELETE FROM notes WHERE original_note_id = ?", (original_id,))
            
            purged_original_notes_count +=1

        conn.commit()
        return purged_original_notes_count

    except sqlite3.Error as e:
        print(f"Database error in purge_deleted_notes: {e}", file=sys.stderr)
        if conn:
            conn.rollback()
        return 0
    except Exception as e:
        print(f"Unexpected error in purge_deleted_notes: {e}", file=sys.stderr)
        if conn:
            conn.rollback()
        return 0
    finally:
        if conn:
            conn.close()

# --- EXPORT/IMPORT FUNCTIONS ---

def export_all_notes() -> Optional[Dict[str, any]]:
    """
    Exports all notes, tags, and their relationships from the database.
    Handles schemas with or without is_deleted/deleted_at columns.
    Returns a dictionary structured for JSON serialization, or None on error.
    """
    conn = None
    export_data: Dict[str, any] = {
        "export_metadata": {
            "format_version": "1.1.0", # Incremented version due to typed tags
            "export_timestamp_utc": datetime.now(timezone.utc).isoformat()
        },
        "tags": [],
        "notes": [],
        "note_tags_relations": []
    }

    try:
        conn = get_db_connection()
        if conn is None:
            print("Database connection not available in export_all_notes.", file=sys.stderr)
            return None
        
        cursor = conn.cursor()

        # 1. Export all tags
        cursor.execute("SELECT tag_id, tag_type, tag_value FROM tags")
        tags_data = cursor.fetchall()
        for tag_row in tags_data:
            export_data["tags"].append(dict(tag_row))

        # 2. Export all note versions - try with new schema first
        notes_data = []
        try:
            cursor.execute(
                "SELECT note_id, original_note_id, content, created_at, "
                "is_latest_version, properties_json, is_deleted, deleted_at "
                "FROM notes"
            )
            notes_data = cursor.fetchall()
            schema_has_delete_columns = True
        except sqlite3.OperationalError as e:
            if "no such column" in str(e).lower() and ("is_deleted" in str(e).lower() or "deleted_at" in str(e).lower()):
                print("Warning: is_deleted/deleted_at columns not found. Exporting with defaults.", file=sys.stderr)
                # Fallback to old schema query
                cursor.execute(
                    "SELECT note_id, original_note_id, content, created_at, "
                    "is_latest_version, properties_json "
                    "FROM notes"
                )
                notes_data = cursor.fetchall()
                schema_has_delete_columns = False
            else:
                raise # Re-raise if it's a different OperationalError

        for note_row_sqlite in notes_data:
            note_dict = dict(note_row_sqlite)
            if not schema_has_delete_columns:
                note_dict['is_deleted'] = 0 # Default for old schema
                note_dict['deleted_at'] = None  # Default for old schema
            
            # Ensure datetime fields are strings for JSON
            # SQLite TIMESTAMPS are often strings already, but direct datetime objects from Python need conversion
            if isinstance(note_dict.get("created_at"), datetime):
                note_dict["created_at"] = note_dict["created_at"].isoformat()
            elif isinstance(note_dict.get("created_at"), str): # Pass through if already string
                pass 

            if note_dict.get("deleted_at") is not None:
                if isinstance(note_dict.get("deleted_at"), datetime):
                    note_dict["deleted_at"] = note_dict["deleted_at"].isoformat()
                elif isinstance(note_dict.get("deleted_at"), str):
                    pass 
            
            export_data["notes"].append(note_dict)

        # 3. Export all note_tags relationships
        cursor.execute("SELECT note_version_id, tag_id FROM note_tags")
        note_tags_data = cursor.fetchall()
        for nt_row in note_tags_data:
            export_data["note_tags_relations"].append(dict(nt_row))
            
        return export_data

    except sqlite3.Error as e:
        print(f"Database error during export_all_notes: {e}", file=sys.stderr)
        return None
    except Exception as e:
        print(f"Unexpected error during export_all_notes: {e}", file=sys.stderr)
        return None
    finally:
        if conn:
            conn.close()

def import_notes_from_json_data(data_to_import: Dict[str, any]) -> bool:
    """
    Imports notes, tags, and their relationships from a dictionary (parsed from JSON).
    This function assumes it's operating on a database that is either empty 
    or where ID conflicts will not be an issue (e.g., after an initdb).
    Returns True on success, False on failure.
    """
    conn = None
    
    # Basic validation of the import structure
    if not all(k in data_to_import for k in ["export_metadata", "tags", "notes", "note_tags_relations"]):
        print("Error: Import data is missing one or more required top-level keys.", file=sys.stderr)
        return False
    
    metadata = data_to_import.get("export_metadata", {})
    imported_format_version = metadata.get("format_version")

    if not imported_format_version:
        print("Error: Import data is missing format_version in metadata.", file=sys.stderr)
        return False
    
    # Define the currently expected import format version
    # This should ideally align with what export_all_notes produces or a compatible version.
    # Based on export_all_notes, this is "1.0.1".
    # With typed tags, the new version is "1.1.0"
    CURRENTLY_SUPPORTED_IMPORT_VERSION = "1.1.0"

    if imported_format_version != CURRENTLY_SUPPORTED_IMPORT_VERSION:
        print(f"Error: Unsupported import format version. Expected '{CURRENTLY_SUPPORTED_IMPORT_VERSION}', but got '{imported_format_version}'.", file=sys.stderr)
        return False

    try:
        conn = get_db_connection()
        if conn is None:
            print("Database connection not available in import_notes_from_json_data.", file=sys.stderr)
            return False
        
        cursor = conn.cursor()

        # Turn off foreign keys to allow inserting with specific IDs and in any order temporarily
        cursor.execute("PRAGMA foreign_keys = OFF;")

        # 1. Import tags
        # Assumes tag_id is INTEGER PRIMARY KEY and can be set if table is empty or ID doesn't exist.
        # If tags table might not be empty and has autoincrement, this direct ID setting might fail.
        # For a clean import, target DB should be empty.
        tags_to_insert = []
        for tag_data in data_to_import.get("tags", []):
            # Ensure tag_type is present, default to general if it was from an older export perhaps (though version check should catch)
            # For 1.1.0, tag_type and tag_value are expected.
            if not all(k in tag_data for k in ["tag_id", "tag_type", "tag_value"]):
                print(f"Warning: Skipping malformed tag data (missing id, type, or value): {tag_data}", file=sys.stderr)
                continue
            tags_to_insert.append((tag_data["tag_id"], tag_data["tag_type"], tag_data["tag_value"]))
        
        if tags_to_insert:
            cursor.executemany("INSERT INTO tags (tag_id, tag_type, tag_value) VALUES (?, ?, ?)", tags_to_insert)

        # 2. Import notes
        # Similar assumption for note_id as for tag_id.
        notes_to_insert = []
        for note_data in data_to_import.get("notes", []):
            # Validate all required fields are present
            required_note_keys = ["note_id", "original_note_id", "content", "created_at", "is_latest_version"]
            if not all(k in note_data for k in required_note_keys):
                print(f"Warning: Skipping malformed note data (missing required keys): {note_data.get('note_id', 'Unknown ID')}", file=sys.stderr)
                continue

            # Handle optional properties_json, is_deleted, deleted_at
            props_json = note_data.get("properties_json") # Can be None
            is_deleted = note_data.get("is_deleted", 0) # Default to 0 (False) if missing
            deleted_at = note_data.get("deleted_at")     # Can be None

            # Ensure boolean values are integers for SQLite
            is_latest_version_int = 1 if note_data["is_latest_version"] else 0
            is_deleted_int = 1 if is_deleted else 0
            
            notes_to_insert.append((
                note_data["note_id"],
                note_data["original_note_id"],
                note_data["content"],
                note_data["created_at"], # Assumed to be ISO string, SQLite handles it
                is_latest_version_int,
                props_json,
                is_deleted_int,
                deleted_at # Assumed to be ISO string or None
            ))

        if notes_to_insert:
            cursor.executemany(
                "INSERT INTO notes (note_id, original_note_id, content, created_at, is_latest_version, properties_json, is_deleted, deleted_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)", 
                notes_to_insert
            )

        # 3. Import note_tags relationships
        note_tags_to_insert = []
        for nt_data in data_to_import.get("note_tags_relations", []):
            if not all(k in nt_data for k in ["note_version_id", "tag_id"]):
                print(f"Warning: Skipping malformed note_tags_relation: {nt_data}", file=sys.stderr)
                continue
            note_tags_to_insert.append((nt_data["note_version_id"], nt_data["tag_id"]))
        
        if note_tags_to_insert:
            cursor.executemany("INSERT INTO note_tags (note_version_id, tag_id) VALUES (?, ?)", note_tags_to_insert)

        # Commit all changes
        conn.commit()

        # Turn foreign keys back on
        cursor.execute("PRAGMA foreign_keys = ON;")
        # Verify foreign keys are now enforced (optional check)
        # fk_check_cursor = conn.cursor()
        # fk_check_cursor.execute("PRAGMA foreign_key_check;")
        # violations = fk_check_cursor.fetchall()
        # if violations:
        #     print(f"Warning: Foreign key violations detected after import: {violations}", file=sys.stderr)
        #     # Potentially rollback or handle error more gracefully
        #     # For now, assume commit succeeded and FKs are fine if no exceptions.
        # fk_check_cursor.close()


        return True

    except sqlite3.IntegrityError as ie:
        # This can happen if trying to insert duplicate primary keys, e.g. tag_id or note_id,
        # or if foreign key constraints fail (though we turned them off for inserts).
        # More likely if DB was not empty.
        print(f"Database integrity error during import: {ie}. This often means the database was not empty or IDs collided.", file=sys.stderr)
        if conn:
            conn.rollback()
        return False
    except sqlite3.Error as e:
        print(f"Database error during import_notes_from_json_data: {e}", file=sys.stderr)
        if conn:
            conn.rollback()
        return False
    except Exception as e:
        print(f"Unexpected error during import_notes_from_json_data: {e}", file=sys.stderr)
        if conn:
            conn.rollback()
        return False
    finally:
        if conn:
            # Ensure foreign keys are attempted to be turned back on even if an error occurred before commit.
            try:
                cursor = conn.cursor() # Re-obtain cursor if previous one is invalid
                cursor.execute("PRAGMA foreign_keys = ON;")
            except sqlite3.Error as fke:
                print(f"Error trying to re-enable foreign keys: {fke}", file=sys.stderr)
            conn.close()

def list_all_tags() -> List[str]:
    """
    Retrieves a list of all unique tag names from the database, sorted alphabetically.
    Returns a list of strings (tag names).
    """
    conn = None
    all_tags: List[str] = []
    try:
        conn = get_db_connection()
        if conn is None:
            print("Database connection not available in list_all_tags.", file=sys.stderr)
            return all_tags # Return empty list

        cursor = conn.cursor()
        # Order by type then value for consistent output
        cursor.execute("SELECT DISTINCT tag_type, tag_value FROM tags ORDER BY tag_type ASC, tag_value ASC")
        rows = cursor.fetchall()
        for row in rows:
            ttype, tvalue = row['tag_type'], row['tag_value']
            if ttype == 'general':
                all_tags.append(tvalue)
            else:
                all_tags.append(f"{ttype}:{tvalue}")

    except sqlite3.Error as e:
        print(f"Database error in list_all_tags: {e}", file=sys.stderr)
        # No rollback needed for SELECT
    except Exception as e:
        print(f"Unexpected error in list_all_tags: {e}", file=sys.stderr)
    finally:
        if conn:
            conn.close()
    return all_tags

# Example of how this might be tested or run directly (for development purposes)
if __name__ == '__main__':
    # Setup sys.path to find database_manager and config if run directly
    # This assumes this script is in KITCore/tools and database_manager is in KITCore/
    # and config.py is in the parent of KITCore (PROJECT_ROOT)
    
    # Determine PROJECT_ROOT based on this file's location
    # (../../ -> moves up from KITCore/tools/ to PROJECT_ROOT)
    PROJECT_ROOT_FOR_TESTING = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
    if PROJECT_ROOT_FOR_TESTING not in sys.path:
        sys.path.insert(0, PROJECT_ROOT_FOR_TESTING)
    
    # Now imports like `from ..database_manager import get_db_connection` work if this file is
    # part of a package structure, but direct execution `python note_tool.py` needs more care.
    # For direct execution, Python treats the script's dir as the top-level package, so `..` fails.
    # One way to handle direct execution for testing is to adjust sys.path to make `KITCore` a package.
    # However, the typical way is to run tests from the project root using `python -m unittest ...`
    # which handles paths correctly.

    # For simple direct testing, let's ensure KITCore is findable for `from ..database_manager ...`
    # This is a bit of a hack for direct script execution. Prefer running via KITCore.py or tests.
    KITCORE_DIR_FOR_TESTING = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    if KITCORE_DIR_FOR_TESTING not in sys.path:
         sys.path.insert(0, KITCORE_DIR_FOR_TESTING) # To find `database_manager` if KITCore itself is not a package in sys.path

    # The following imports are now attempted as if `note_tool.py` is part of a package
    # but `database_manager` might not be found correctly if this file is the entry point.
    # For this direct test, we'll re-import database_manager assuming path is set up.
    try:
        from KITCore.database_manager import create_tables, get_db_connection
        print("Attempting to initialize DB for note_tool.py direct test...")
        # Ensure tables exist for testing
        # create_tables() # This would call get_db_connection from database_manager
        
        # We should call create_tables from database_manager.py to ensure it's working
        # Need to ensure its get_db_connection is used.
        # The `from ..database_manager import get_db_connection` handles this for the module's functions.
        
        # For a quick test, let's use the functions directly if db is set up
        print("--- Testing create_note ---")
        note_id1 = create_note("Test note 1 for direct run", ["test", "python"], {"source": "direct_run"})
        if note_id1:
            print(f"Created note 1 with ID: {note_id1}")
            note_id2 = create_note("Another test note for direct run", ["Test", "Sample"], {"status": "draft"})
            if note_id2:
                print(f"Created note 2 with ID: {note_id2}")

            print("--- Testing find_notes ---")
            found = find_notes(content_keywords=["another test"])
            print(f"Found notes with content 'another test': {json.dumps(found, indent=2)}")
            
            found_content = find_notes(content_keywords=["another test"])
            print(f"Found notes with content 'another test': {json.dumps(found_content, indent=2)}")

            print("--- Testing update_note ---")
            if note_id1:
                updated_id = update_note(note_id1, new_content="Updated content for note 1", new_tags_list=["test", "updated"], new_properties_dict={"source":"direct_run_update", "version": 2})
                if updated_id:
                    print(f"Updated note 1. New version ID: {updated_id}")
                    
                    print("--- Testing get_note_history ---")
                    history = get_note_history(note_id1)
                    print(f"History for note original_id {note_id1}: {json.dumps(history, indent=2)}")
                else:
                    print(f"Failed to update note {note_id1}")
            else:
                 print("Skipping update/history tests as note_id1 was not created.")
        else:
            print("Failed to create initial note for testing. Ensure database is accessible and schema is correct.")
            print("Try running KITCore.py initdb first from the project root.")

    except ImportError as e:
        print(f"ImportError during direct test: {e}")
        print("Please ensure you run this test from the project root, or that PYTHONPATH is correctly set.")
        print("Example: python -m KITCore.tools.note_tool")
    except Exception as e:
        print(f"An error occurred during direct testing of note_tool.py: {e}")

    # Clean up test data? This is tricky if run multiple times.
    # For unit tests, a dedicated test DB is better. 