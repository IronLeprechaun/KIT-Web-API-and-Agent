from fastapi import APIRouter, HTTPException, Depends, Body, WebSocket, WebSocketDisconnect
from typing import List, Optional, Dict, Any
from pydantic import BaseModel
from ..auth_utils import get_current_user, oauth2_scheme # New import
import sys
import os
import json # For WebSocket communication
import logging # Added for logging

# Configure logger for this module
logger = logging.getLogger(__name__)

# Adjust path to import AIService
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..')) # Add backend directory to sys.path
from api.services.ai_service import AIService

router = APIRouter(
    prefix="/ai",
    tags=["ai"]
    # dependencies=[Depends(get_current_user)] # Temporarily disabled for WebSocket testing
)

# Pydantic Models for AI interaction
class AIQuery(BaseModel):
    query: str
    conversation_history: Optional[List[Dict[str, str]]] = [] # e.g., [{"role": "user", "text": "..."}, {"role": "model", "text": "..."}]
    user_name: Optional[str] = None # For personalization

class AIResponse(BaseModel):
    response_text: str
    # Potentially add other fields like suggested_actions, identified_intent, etc.

# AI Service Instance
ai_service = AIService()

@router.post("/process", response_model=AIResponse, summary="Process a natural language query using the AI agent")
async def process_ai_query(ai_query: AIQuery = Body(...)):
    try:
        response = await ai_service.process_user_query(
            user_query=ai_query.query,
            conversation_history=ai_query.conversation_history,
            user_name=ai_query.user_name
        )
        # The response from ai_service.process_user_query should ideally be structured.
        # For now, we assume it returns a dict that can be unpacked into AIResponse.
        # Example: {"response_text": "...", ...}
        return AIResponse(**response)
    except Exception as e:
        # Log the exception details (e)
        raise HTTPException(status_code=500, detail=f"Error processing AI query: {str(e)}")

@router.websocket("/ws")
async def ai_websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    # Authentication will be revisited later.

    try:
        while True:
            data = await websocket.receive_text()
            try:
                payload = json.loads(data)
                query = payload.get("query")
                history = payload.get("conversation_history", [])
                user_name = payload.get("user_name")

                if query is None:
                    await websocket.send_text(json.dumps({"error": "Query cannot be null"}))
                    continue

                # Stream responses if your AI service supports it, or send full response
                # For simplicity, this example sends a full response after processing.
                response_data = await ai_service.process_user_query(
                    user_query=query,
                    conversation_history=history,
                    user_name=user_name
                )
                await websocket.send_text(json.dumps(response_data))

            except json.JSONDecodeError:
                await websocket.send_text(json.dumps({"error": "Invalid JSON payload"}))
            except Exception as e:
                # Log the exception e
                await websocket.send_text(json.dumps({"error": f"Error processing AI query: {str(e)}"}))
    except WebSocketDisconnect:
        logger.info("Client disconnected from AI WebSocket")
    except Exception as e:
        # Log unexpected errors
        logger.error(f"Unexpected WebSocket error: {e}", exc_info=True)
        # Ensure the websocket is closed if an error occurs that isn't a WebSocketDisconnect
        if websocket.client_state != websocket.client_state.DISCONNECTED:
            await websocket.close(code=1011) # Internal Error 