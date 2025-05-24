import sys
import os
from typing import List, Optional, Dict, Any
from datetime import datetime
import logging # Import logging

# Get a logger for this module
logger = logging.getLogger(__name__)

# Add the parent directory to sys.path to import KITCore
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from KITCore.tools.note_tool import (
    create_note,
    find_notes,
    update_note,
    get_note_history,
    soft_delete_note,
    restore_note,
    get_deleted_notes,
    purge_deleted_notes,
    add_tag_to_note,
    remove_tag_from_note,
    export_all_notes,
    import_notes_from_json_data
)

class NoteService:
    @staticmethod
    async def create_note(content: str, tags: Optional[List[str]] = None, properties: Optional[Dict[str, Any]] = None):
        try:
            return create_note(content, tags, properties)
        except Exception as e:
            raise Exception(f"Failed to create note: {str(e)}")

    @staticmethod
    async def find_notes(
        keywords: Optional[List[str]] = None,
        include_tags: Optional[List[str]] = None,
        exclude_tags: Optional[List[str]] = None,
        any_of_tags: Optional[List[str]] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        original_note_ids: Optional[List[int]] = None,
        specific_version_ids: Optional[List[int]] = None
    ):
        try:
            logger.info(f"Finding notes with keywords: {keywords}, include_tags: {include_tags}, exclude_tags: {exclude_tags}, any_of_tags: {any_of_tags}, start_date: {start_date}, end_date: {end_date}, original_note_ids: {original_note_ids}, specific_version_ids: {specific_version_ids}")
            notes_result = find_notes(content_keywords=keywords, 
                                      include_tags=include_tags,
                                      exclude_tags=exclude_tags,
                                      any_of_tags=any_of_tags,
                                      date_range=(start_date, end_date), 
                                      original_note_ids=original_note_ids,
                                      specific_version_ids=specific_version_ids)
            logger.info(f"Found {len(notes_result) if notes_result else 0} notes.")
            return notes_result
        except Exception as e:
            logger.error(f"Error finding notes: {str(e)}", exc_info=True)
            raise Exception(f"Failed to find notes: {str(e)}")

    @staticmethod
    async def update_note(
        original_id: int,
        new_content: Optional[str] = None,
        new_tags: Optional[List[str]] = None,
        new_properties: Optional[Dict[str, Any]] = None
    ):
        try:
            return update_note(original_id, new_content, new_tags, new_properties)
        except Exception as e:
            raise Exception(f"Failed to update note: {str(e)}")

    @staticmethod
    async def get_note_history(original_id: int):
        try:
            return get_note_history(original_id)
        except Exception as e:
            raise Exception(f"Failed to get note history: {str(e)}")

    @staticmethod
    async def soft_delete_note(original_id: int):
        try:
            return soft_delete_note(original_id)
        except Exception as e:
            raise Exception(f"Failed to soft delete note: {str(e)}")

    @staticmethod
    async def restore_note(original_id: int):
        try:
            return restore_note(original_id)
        except Exception as e:
            raise Exception(f"Failed to restore note: {str(e)}")

    @staticmethod
    async def get_deleted_notes():
        try:
            return get_deleted_notes()
        except Exception as e:
            raise Exception(f"Failed to get deleted notes: {str(e)}")

    @staticmethod
    async def purge_deleted_notes(older_than_days: Optional[int] = None):
        try:
            return purge_deleted_notes(older_than_days)
        except Exception as e:
            raise Exception(f"Failed to purge deleted notes: {str(e)}")

    @staticmethod
    async def add_tags_to_note(original_id: int, tags_to_add: List[str]):
        """Adds a list of tags to a note."""
        if not isinstance(tags_to_add, list):
            logger.error(f"add_tags_to_note received non-list for tags_to_add: {tags_to_add}")
            # Or raise an error, depending on desired strictness
            return None 

        successfully_added_count = 0
        try:
            for tag_name in tags_to_add:
                if not isinstance(tag_name, str) or not tag_name.strip():
                    logger.warning(f"Skipping invalid tag_name: '{tag_name}' for note original_id: {original_id}")
                    continue
                
                cleaned_tag_name = tag_name.strip() # Assuming core tool handles # removal if necessary, or it's already clean
                logger.info(f"Service attempting to add tag '{cleaned_tag_name}' to note original_id: {original_id}")
                # KITCore.tools.note_tool.add_tag_to_note returns the new note_version_id or None
                result = add_tag_to_note(original_note_id=original_id, tag_to_add=cleaned_tag_name)
                if result is not None:
                    logger.info(f"Successfully added tag '{cleaned_tag_name}' to note original_id: {original_id}. New version ID: {result}")
                    successfully_added_count += 1
                else:
                    logger.warning(f"Failed to add tag '{cleaned_tag_name}' to note original_id: {original_id} (core tool returned None).")
            
            if successfully_added_count > 0:
                # Fetch and return the updated note
                # Assuming find_notes can take a single original_id and returns a list
                updated_notes = await NoteService.find_notes(original_note_ids=[original_id])
                if updated_notes and len(updated_notes) == 1:
                    logger.info(f"Returning updated note original_id: {original_id} after adding {successfully_added_count} tags.")
                    return updated_notes[0]
                else:
                    logger.error(f"Failed to retrieve updated note original_id: {original_id} after adding tags.")
                    return None # Or raise an error
            elif tags_to_add: # Attempted to add tags, but all failed
                logger.warning(f"No tags were successfully added to note original_id: {original_id} out of {len(tags_to_add)} attempted.")
                return None # Indicate no change or partial success leading to no fetch
            else: # No tags were provided to add
                logger.info(f"No tags provided to add to note original_id: {original_id}. Returning None.")
                return None

        except Exception as e:
            logger.error(f"Error in NoteService adding tags {tags_to_add} to note {original_id}: {str(e)}", exc_info=True)
            raise Exception(f"Failed to add tags: {str(e)}") 

    @staticmethod
    async def update_note_content(original_id: int, new_content: str) -> Optional[Dict[str, Any]]:
        """Updates only the content of a note."""
        try:
            logger.info(f"Service attempting to update content for note original_id: {original_id}")
            # Call the existing core update_note, passing only new_content
            # The core tool should handle creating a new version and preserving existing tags/properties
            new_version_id = update_note(original_note_id_to_update=original_id, new_content=new_content)
            
            if new_version_id is not None:
                logger.info(f"Successfully updated content for note original_id: {original_id}. New version ID: {new_version_id}")
                # Fetch and return the updated note to include in AI action_data
                updated_notes = await NoteService.find_notes(original_note_ids=[original_id])
                if updated_notes and len(updated_notes) == 1:
                    return updated_notes[0]
                else:
                    logger.error(f"Failed to retrieve updated note original_id: {original_id} after content update.")
                    # Even if fetch fails, the update might have succeeded. 
                    # Consider returning a simpler success indicator or just the ID.
                    # For now, returning None if fetch fails to be consistent with add_tags_to_note error handling.
                    return None 
            else:
                logger.warning(f"Failed to update content for note original_id: {original_id} (core tool returned None).")
                return None
        except Exception as e:
            logger.error(f"Error in NoteService updating content for note {original_id}: {str(e)}", exc_info=True)
            raise Exception(f"Failed to update note content: {str(e)}") 

    @staticmethod
    async def update_note_properties(original_id: int, properties_to_update: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Updates only the JSON properties of a note."""
        try:
            logger.info(f"Service attempting to update properties for note original_id: {original_id} with {properties_to_update}")
            # Call the existing core update_note, passing only new_properties_dict
            # The core tool should handle creating a new version, preserving existing content/tags, and merging properties.
            new_version_id = update_note(original_note_id_to_update=original_id, new_properties_dict=properties_to_update)
            
            if new_version_id is not None:
                logger.info(f"Successfully updated properties for note original_id: {original_id}. New version ID: {new_version_id}")
                # Fetch and return the updated note to include in AI action_data
                updated_notes = await NoteService.find_notes(original_note_ids=[original_id])
                if updated_notes and len(updated_notes) == 1:
                    return updated_notes[0]
                else:
                    logger.error(f"Failed to retrieve updated note original_id: {original_id} after properties update.")
                    return None 
            else:
                logger.warning(f"Failed to update properties for note original_id: {original_id} (core tool returned None).")
                return None
        except Exception as e:
            logger.error(f"Error in NoteService updating properties for note {original_id}: {str(e)}", exc_info=True)
            raise Exception(f"Failed to update note properties: {str(e)}") 

    @staticmethod
    async def remove_tags_from_note(original_id: int, tags_to_remove: List[str]) -> Optional[Dict[str, Any]]:
        """Removes multiple tags from a note by creating a new version."""
        try:
            logger.info(f"Service attempting to remove tags {tags_to_remove} from note original_id: {original_id}")
            # Remove tags one by one (note tool handles single tag removal)
            # This creates multiple versions but is simpler than modifying core tool
            updated_note = None
            current_id = original_id
            
            for tag_to_remove in tags_to_remove:
                if tag_to_remove.strip():  # Skip empty tags
                    new_version_id = remove_tag_from_note(current_id, tag_to_remove.strip())
                    if new_version_id is not None:
                        logger.info(f"Successfully removed tag '{tag_to_remove}' from note {current_id}. New version ID: {new_version_id}")
                        # Update current_id for next removal (all removals apply to latest version)
                        current_id = original_id  # Always work on same original ID
                    else:
                        logger.warning(f"Failed to remove tag '{tag_to_remove}' from note {current_id}")
                        
            # Fetch and return the final updated note
            if current_id == original_id:  # At least one removal attempted
                updated_notes = await NoteService.find_notes(original_note_ids=[original_id])
                if updated_notes and len(updated_notes) == 1:
                    updated_note = updated_notes[0]
                    logger.info(f"Successfully removed tags from note {original_id}")
                    return updated_note
                else:
                    logger.error(f"Failed to retrieve updated note original_id: {original_id} after tag removal.")
                    return None
            else:
                logger.warning(f"No valid tags to remove from note {original_id}")
                return None
                
        except Exception as e:
            logger.error(f"Error in NoteService removing tags from note {original_id}: {str(e)}", exc_info=True)
            raise Exception(f"Failed to remove tags from note: {str(e)}")

    @staticmethod
    async def export_notes() -> Optional[Dict[str, Any]]:
        """Exports all notes to a structured dictionary."""
        try:
            logger.info("Service attempting to export all notes")
            export_data = export_all_notes()
            if export_data:
                logger.info(f"Successfully exported notes data with {len(export_data.get('notes', []))} notes")
                return export_data
            else:
                logger.warning("Export returned no data")
                return None
        except Exception as e:
            logger.error(f"Error in NoteService exporting notes: {str(e)}", exc_info=True)
            raise Exception(f"Failed to export notes: {str(e)}")

    @staticmethod
    async def import_notes(import_data: Dict[str, Any]) -> bool:
        """Imports notes from a structured dictionary."""
        try:
            logger.info("Service attempting to import notes")
            success = import_notes_from_json_data(import_data)
            if success:
                logger.info("Successfully imported notes data")
                return True
            else:
                logger.warning("Import failed")
                return False
        except Exception as e:
            logger.error(f"Error in NoteService importing notes: {str(e)}", exc_info=True)
            raise Exception(f"Failed to import notes: {str(e)}") 