from fastapi import APIRouter, HTTPException, Depends
from typing import List, Optional
from pydantic import BaseModel
from ..auth_utils import get_current_user
# Ensure services are correctly imported
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..')) # Add backend directory to sys.path
from api.services.tag_service import TagService

router = APIRouter(
    prefix="/tags",
    tags=["tags"],
    # dependencies=[Depends(get_current_user)] # Temporarily disabled for testing
)

# Pydantic models
class TagBase(BaseModel):
    name: str

class TagCreate(TagBase):
    pass

class Tag(TagBase):
    id: int
    # Add other relevant fields if your Tag model in KITCore has them

    class Config:
        from_attributes = True

class NoteTagLink(BaseModel):
    note_original_id: int
    tag_name: str

# Instance of the service
tag_service = TagService()

@router.post("/", response_model=Tag, summary="Create a new tag (globally, not linked to a note yet)")
async def create_tag(tag: TagCreate):
    # This endpoint might be less used if tags are implicitly created when added to notes.
    # KITCore's note_tool.py does not have a standalone create_tag function.
    # Tags are created when a note is created or updated with new tags.
    # For now, this will be a placeholder or you might decide to add such functionality to KITCore.
    raise HTTPException(status_code=501, detail="Standalone tag creation not implemented in KITCore. Tags are created with notes.")

@router.get("/", response_model=List[Tag], summary="List all unique tags known to the system")
async def list_all_tags():
    try:
        tags_data = await tag_service.list_all_tags()
        # Assuming tags_data is a list of tuples (id, name) or similar that Pydantic can handle
        return [Tag(id=idx, name=tag_name) for idx, tag_name in enumerate(tags_data)] # Assign dummy IDs for now
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/notes/add", summary="Add a tag to a specific note")
async def add_tag_to_note_endpoint(link: NoteTagLink):
    try:
        updated_note = await tag_service.add_tag_to_note(link.note_original_id, link.tag_name)
        if not updated_note:
            raise HTTPException(status_code=404, detail="Note not found or tag could not be added")
        return {"message": f"Tag '{link.tag_name}' added to note {link.note_original_id}", "note": updated_note}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/notes/remove", summary="Remove a tag from a specific note")
async def remove_tag_from_note_endpoint(link: NoteTagLink):
    try:
        updated_note = await tag_service.remove_tag_from_note(link.note_original_id, link.tag_name)
        if not updated_note:
            raise HTTPException(status_code=404, detail="Note not found or tag could not be removed")
        return {"message": f"Tag '{link.tag_name}' removed from note {link.note_original_id}", "note": updated_note}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) 