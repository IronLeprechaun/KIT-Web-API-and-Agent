import sys
import os
from typing import List, Optional, Any, Dict

# Adjust the path to import from KITCore which is now two levels up from api/services
# and then into KITCore/tools
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from KITCore.tools.note_tool import (
    add_tag_to_note as kit_add_tag_to_note,
    remove_tag_from_note as kit_remove_tag_from_note,
    list_all_tags as kit_list_all_tags
)

class TagService:
    @staticmethod
    async def list_all_tags() -> List[str]:
        """Lists all unique tags known to the system."""
        try:
            # kit_list_all_tags returns a list of tag names (strings)
            return kit_list_all_tags()
        except Exception as e:
            # Log the exception e
            raise Exception(f"Failed to list all tags: {str(e)}")

    @staticmethod
    async def add_tag_to_note(original_note_id: int, tag_to_add: str) -> Optional[Dict[str, Any]]:
        """Adds a single tag to an existing note, creating a new version."""
        try:
            # kit_add_tag_to_note returns the updated note details or None
            updated_note = kit_add_tag_to_note(original_note_id, tag_to_add)
            return updated_note # This could be a dict representing the note
        except Exception as e:
            # Log the exception e
            raise Exception(f"Failed to add tag '{tag_to_add}' to note {original_note_id}: {str(e)}")

    @staticmethod
    async def remove_tag_from_note(original_note_id: int, tag_to_remove: str) -> Optional[Dict[str, Any]]:
        """Removes a single tag from an existing note, creating a new version."""
        try:
            # kit_remove_tag_from_note returns the new version ID or None
            new_version_id = kit_remove_tag_from_note(original_note_id, tag_to_remove)
            if new_version_id is not None:
                # Fetch the updated note to return complete data
                from api.services.note_service import NoteService
                updated_notes = await NoteService.find_notes(original_note_ids=[original_note_id])
                if updated_notes and len(updated_notes) == 1:
                    return updated_notes[0]
            return None
        except Exception as e:
            # Log the exception e
            raise Exception(f"Failed to remove tag '{tag_to_remove}' from note {original_note_id}: {str(e)}") 