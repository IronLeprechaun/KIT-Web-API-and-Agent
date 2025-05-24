from fastapi import APIRouter, HTTPException, Depends
from typing import List, Optional
from pydantic import BaseModel
from datetime import datetime
from ..auth_utils import get_current_user
from ..services.note_service import NoteService
import logging

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/notes",
    tags=["notes"],
    # dependencies=[Depends(get_current_user)] # Temporarily disabled for testing
)

# Pydantic models
class NoteBase(BaseModel):
    content: str
    tags: Optional[List[str]] = []
    properties: Optional[dict] = {}

class NoteCreate(NoteBase):
    pass

class NoteUpdate(NoteBase):
    pass

class Note(NoteBase):
    id: int
    original_note_id: Optional[int] = None
    created_at: datetime
    is_latest_version: Optional[bool] = None
    is_deleted: bool = False
    deleted_at: Optional[datetime] = None

    title: Optional[str] = None

    class Config:
        from_attributes = True

# Routes
@router.post("/", response_model=Note, status_code=201)
async def create_note_route(note_data: NoteCreate):
    logger.info(f"Received request to create note: {note_data.model_dump_json(indent=2)}")
    try:
        new_note_original_id = await NoteService.create_note(
            content=note_data.content,
            tags=note_data.tags,
            properties=note_data.properties
        )
        logger.info(f"Note created by NoteService, original_id: {new_note_original_id}")

        if new_note_original_id is None:
            logger.error("NoteService.create_note returned None, indicating creation failure.")
            raise HTTPException(status_code=500, detail="Failed to create note in core system.")

        # Fetch the newly created note to get its full details
        fetched_notes = await NoteService.find_notes(original_note_ids=[new_note_original_id])
        
        if not fetched_notes or len(fetched_notes) == 0:
            logger.error(f"Failed to fetch note (original_id: {new_note_original_id}) after creation.")
            raise HTTPException(status_code=500, detail="Failed to retrieve note after creation.")
        
        # Assuming find_notes returns a list, and we expect one note for the new ID
        core_dict = fetched_notes[0]
        if not isinstance(core_dict, dict):
             logger.error(f"Fetched note (original_id: {new_note_original_id}) is not a dict: {core_dict}")
             raise HTTPException(status_code=500, detail="Invalid note data retrieved after creation.")

        response_data = {
            "id": core_dict.get("note_id", core_dict.get("id")),
            "content": core_dict.get("content"),
            "created_at": core_dict.get("created_at", datetime.utcnow()),
            "tags": core_dict.get("tags", []),
            "properties": core_dict.get("properties", {}),
            "title": core_dict.get("title", core_dict.get("content", "")[:30]),
            "original_note_id": core_dict.get("original_note_id"),
            "is_latest_version": core_dict.get("is_latest_version"),
        }
        return Note(**response_data)
    except Exception as e:
        logger.error(f"Error creating note: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/", response_model=List[Note])
async def get_notes_route(
    tags: Optional[List[str]] = None,
    keywords: Optional[List[str]] = None,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None
):
    logger.info(f"Received request to get notes with tags: {tags}, keywords: {keywords}, start: {start_date}, end: {end_date}")
    try:
        notes_from_service = await NoteService.find_notes(tags, keywords, start_date, end_date)
        logger.info(f"Notes received from service: {len(notes_from_service) if notes_from_service else 0} notes")
        
        response_notes = []
        if notes_from_service:
            for core_note in notes_from_service:
                if not isinstance(core_note, dict):
                    try:
                        core_dict = dict(core_note)
                    except TypeError:
                        logger.error(f"Could not convert core_note to dict: {core_note}")
                        continue
                else:
                    core_dict = core_note
                
                note_id = core_dict.get("note_id", core_dict.get("id"))
                if note_id is None:
                    logger.warning(f"Skipping note due to missing 'id' or 'note_id'. Data: {core_dict}")
                    continue

                response_data = {
                    "id": note_id, 
                    "content": core_dict.get("content"),
                    "created_at": core_dict.get("created_at", datetime.utcnow()), 
                    "tags": core_dict.get("tags", []),
                    "properties": core_dict.get("properties", {}),
                    "title": core_dict.get("title", core_dict.get("content", "")[:30]), 
                    "original_note_id": core_dict.get("original_note_id"),
                    "is_latest_version": core_dict.get("is_latest_version"),
                    "is_deleted": core_dict.get("is_deleted", False),
                    "deleted_at": core_dict.get("deleted_at")
                }
                try:
                    response_notes.append(Note(**response_data))
                except Exception as pydantic_error:
                    logger.error(f"Pydantic validation error for note ID {response_data.get('id')}: {pydantic_error}. Data: {response_data}")

        logger.info(f"Returning {len(response_notes)} notes to client.")
        return response_notes
    except Exception as e:
        logger.error(f"Error getting notes: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{note_id}", response_model=Note)
async def get_note_route(note_id: int):
    logger.info(f"Received request to get note with ID: {note_id}")
    try:
        notes_from_service = await NoteService.find_notes(specific_version_ids=[note_id])
        if not notes_from_service:
            logger.warning(f"Note with ID {note_id} not found by NoteService.")
            raise HTTPException(status_code=404, detail=f"Note with ID {note_id} not found")

        core_dict = notes_from_service[0] # Should be only one note
        if not isinstance(core_dict, dict):
            logger.error(f"Fetched note (ID: {note_id}) is not a dict: {core_dict}")
            raise HTTPException(status_code=500, detail="Invalid note data retrieved.")

        # Optionally, decide if soft-deleted notes should be returned by this direct ID lookup.
        # For now, let's assume if it's found by specific ID, it's returned regardless of is_deleted.
        # The Pydantic model Note includes is_deleted and deleted_at fields.

        response_data = {
            "id": core_dict.get("note_id", core_dict.get("id")),
            "content": core_dict.get("content"),
            "created_at": core_dict.get("created_at", datetime.utcnow()),
            "tags": core_dict.get("tags", []),
            "properties": core_dict.get("properties", {}),
            "title": core_dict.get("title", core_dict.get("content", "")[:30]),
            "original_note_id": core_dict.get("original_note_id"),
            "is_latest_version": core_dict.get("is_latest_version"),
            "is_deleted": core_dict.get("is_deleted", False),
            "deleted_at": core_dict.get("deleted_at")
        }
        return Note(**response_data)
    except HTTPException: # Re-raise HTTPExceptions directly
        raise
    except Exception as e:
        logger.error(f"Error getting note {note_id}: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@router.put("/{note_id}", response_model=Note)
async def update_note_route(note_id: int, note_data: NoteUpdate):
    logger.info(f"Received request to update note {note_id}: {note_data.model_dump_json(indent=2)}")
    try:
        logger.warning(f"Update note {note_id} not fully implemented.")
        raise HTTPException(status_code=501, detail="Not implemented")
    except Exception as e:
        logger.error(f"Error updating note {note_id}: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/{note_id}", status_code=204)
async def delete_note_route(note_id: int):
    logger.info(f"Received request to delete note with ID: {note_id}")
    try:
        # First, fetch the note to get its original_note_id, as soft_delete_note expects original_note_id
        # and to confirm the note exists before attempting deletion.
        notes_from_service = await NoteService.find_notes(specific_version_ids=[note_id])
        if not notes_from_service:
            logger.warning(f"Note with ID {note_id} not found for deletion.")
            raise HTTPException(status_code=404, detail=f"Note with ID {note_id} not found")
        
        # We assume find_notes with specific_version_ids returns a list with one item if found
        note_to_delete = notes_from_service[0]
        original_id_to_delete = note_to_delete.get("original_note_id")

        if original_id_to_delete is None:
            # This case should ideally not happen if the note was found and has a proper structure.
            # It might imply that the note_id itself was an original_note_id, or data integrity issue.
            # For now, if original_note_id is missing from a supposedly valid note, treat it as an error.
            logger.error(f"Cannot delete note ID {note_id}: original_note_id is missing from the fetched note data.")
            raise HTTPException(status_code=500, detail="Failed to identify original note for deletion.")

        logger.info(f"Attempting to soft delete note with original_id: {original_id_to_delete} (derived from version_id: {note_id})")
        success = await NoteService.soft_delete_note(original_id=original_id_to_delete)
        
        if not success:
            # soft_delete_note in note_tool returns True on success, False otherwise.
            # This could mean the note was already deleted or another issue occurred.
            logger.warning(f"Failed to soft delete note with original_id: {original_id_to_delete}. It might have been already deleted or an error occurred.")
            # Depending on strictness, we might return 404 if it implies not found, or 500 if it implies an operational error.
            # For now, let's assume if soft_delete_note returns False, it's a situation where the note wasn't in a state to be deleted (e.g. already deleted)
            # or an actual error. A 404 if it was not found is already handled. If found but delete failed, it is an issue.
            # Let's ensure a clear message if it failed.
            # For simplicity, if it wasn't a 404 initially, but soft_delete_note fails, it implies an issue with the delete operation itself.
            raise HTTPException(status_code=500, detail=f"Failed to delete note with original ID {original_id_to_delete}.")
        
        logger.info(f"Successfully soft-deleted note with original_id: {original_id_to_delete} (triggered by version_id: {note_id})")
        # For 204 No Content, we don't return a body.
        return

    except HTTPException: # Re-raise HTTPExceptions directly
        raise
    except Exception as e:
        logger.error(f"Error deleting note {note_id}: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{note_id}/history", response_model=List[Note])
async def get_note_history_route(note_id: int):
    logger.info(f"Received request for history of note {note_id}")
    try:
        logger.warning(f"History for note {note_id} not fully implemented.")
        raise HTTPException(status_code=501, detail="Not implemented")
    except Exception as e:
        logger.error(f"Error getting history for note {note_id}: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e)) 