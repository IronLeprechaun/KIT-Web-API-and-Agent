import sys
import os
# import inspect # Removed for debugging

# Print statements for immediate debugging, will show in Uvicorn console
print(f"AI_SERVICE_DEBUG: Python executable: {sys.executable}", file=sys.stderr)
print(f"AI_SERVICE_DEBUG: Python version: {sys.version}", file=sys.stderr)
print(f"AI_SERVICE_DEBUG: sys.path: {sys.path}", file=sys.stderr)
print(f"AI_SERVICE_DEBUG: Current working directory: {os.getcwd()}", file=sys.stderr)
try:
    import google.generativeai
    print(f"AI_SERVICE_DEBUG: Successfully imported google.generativeai version: {google.generativeai.__version__}", file=sys.stderr)
except ImportError as e:
    print(f"AI_SERVICE_DEBUG: Failed to import google.generativeai: {e}", file=sys.stderr)
    # Optionally print traceback to stderr as well
    import traceback
    traceback.print_exc(file=sys.stderr)

# Attempting import again here to see if it's available at runtime if not at startup
try:
    import google.generativeai as genai
    print("AI_SERVICE_DEBUG: google.generativeai imported successfully at top level.", file=sys.stderr)
except ImportError:
    print("AI_SERVICE_DEBUG: Failed to import google.generativeai at top level.", file=sys.stderr)
    genai = None # Ensure genai is defined

from typing import List, Optional, Dict, Any, Tuple
import asyncio # For running synchronous KIT.py code in async context
import subprocess # To call KIT.py as a subprocess
import json
import logging
from datetime import datetime # For timestamp
from KIT.logger_utils import setup_kit_loggers
from KITCore.tools.settings_tool import get_setting as kit_get_setting
from api.services.note_service import NoteService
from api.services.tag_service import TagService
from api.services.settings_service import SettingsService
from ..config_settings import MAX_AISERVICE_LOG_FILES # Added

# Configure logging for this module (used for pre-init or static method logging if any)
module_logger = logging.getLogger(__name__) # Renamed to avoid confusion with self.agent_logger
module_logger.info(f"Python executable: {sys.executable}")
module_logger.info(f"Python version: {sys.version}")
module_logger.info(f"sys.path: {sys.path}")
module_logger.info(f"Current working directory: {os.getcwd()}")
try:
    if genai:
        module_logger.info(f"Successfully imported google.generativeai version: {genai.__version__}")
    else:
        module_logger.error("google.generativeai was not imported successfully.")
except Exception as e:
    module_logger.error(f"Error checking google.generativeai version: {e}", exc_info=True)

# Adjust path for KITCore and KIT imports
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..', '..'))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT) # Insert at the beginning
    print(f"AI_SERVICE_DEBUG: Inserted PROJECT_ROOT {PROJECT_ROOT} into sys.path", file=sys.stderr)

# --- Add a more targeted sys.path print here ---
# print(f"AI_SERVICE_DEBUG: sys.path before importing KIT.logger_utils: {sys.path}", file=sys.stderr) # Removed
# --- End targeted print ---

from KIT.gemini_client import GeminiClient
from KIT.logger_utils import setup_kit_loggers
from KITCore.tools.settings_tool import get_setting as kit_get_setting
from api.services.note_service import NoteService
from api.services.tag_service import TagService
from api.services.settings_service import SettingsService

# Predefined help message for the AI
KIT_AI_HELP_MESSAGE = """I can help you manage your notes! Here are some things you can ask me to do:

*   **Create notes:** Just tell me what the note should say. You can also include tags like #shopping or #work.
    *   Example: "Create a note: Remember to buy milk #groceries"
*   **Find notes:** Ask me to find notes using keywords or tags.
    *   Example: "Find notes about project alpha" or "Show me my #urgent notes"
*   **Find a specific note by ID:** If you know the ID of a note.
    *   Example: "Find note ID 123"
*   **Add tags to a note:** Tell me the note ID and the tags you want to add.
    *   Example: "Add the tag #important to note ID 123"
*   **Delete notes:** You can ask me to delete a specific note by its ID, or multiple notes by their IDs.
    *   Example: "Delete note ID 123" or "Delete notes 123 and 456"

I\'m always learning, so if something doesn\'t work as expected, try rephrasing your request!
For actions like deleting or adding tags, I\'ll usually need the note\'s ID if it wasn\'t just created or mentioned.
"""

class AIService:

    def __init__(self):
        self.run_ts = datetime.now().strftime("%Y%m%d_%H%M%S_api_service_init")
        # Use module_logger before self.agent_logger is initialized
        module_logger.debug(f"AIService __init__ called. PROJECT_ROOT: {PROJECT_ROOT}")
        
        self.log_dir = os.path.join(PROJECT_ROOT, "backend", "logs") 
        os.makedirs(self.log_dir, exist_ok=True) 
        module_logger.debug(f"AIService log_dir configured: {self.log_dir}")
        
        self.model_dir = os.path.join(PROJECT_ROOT, "backend", "models")
        self.db_path = os.path.join(PROJECT_ROOT, "backend", "KITCore", "database", "kit_agent.db")
        # self.initialize_logging(service_name="AIService") # This method is not defined

        try:
            self.enable_trace_logging = kit_get_setting("ENABLE_TRACE_LOGGING")
            if not isinstance(self.enable_trace_logging, bool):
                if isinstance(self.enable_trace_logging, str):
                    self.enable_trace_logging = self.enable_trace_logging.lower() == 'true'
                else:
                    self.enable_trace_logging = False 
        except Exception as e:
            print(f"Error fetching ENABLE_TRACE_LOGGING setting: {e}", file=sys.stderr)
            self.enable_trace_logging = False

        # Debug: Print signature of imported setup_kit_loggers
        # try:
        #     print(f"AI_SERVICE_DEBUG: setup_kit_loggers signature: {inspect.signature(setup_kit_loggers)}", file=sys.stderr) # Removed
        # except Exception as e:
        #     print(f"AI_SERVICE_DEBUG: Error inspecting signature: {e}", file=sys.stderr) # Removed

        self.agent_logger, self.trace_logger = setup_kit_loggers(
            self.run_ts,
            trace_enabled_for_session=self.enable_trace_logging,
            max_log_files=MAX_AISERVICE_LOG_FILES
        )

        self.agent_logger.info("AIService initialized and logger configured.")

        self.ai_model_to_use = "gemini-1.5-flash-latest"
        self.agent_logger.info(f"AIService: Configured to use Gemini model: {self.ai_model_to_use}")

        self.kit_system_prompt = """You are KIT, a helpful AI assistant integrated into a personal management system. Your primary purpose is to assist users with managing their notes, tasks, and system settings through a conversational interface. When a user asks for an action that you can perform (like creating, finding, or deleting a note), you should first respond with a natural language confirmation or answer. Then, on a new line, provide a JSON object detailing the recognized intent and the entities extracted from the user's query. Do not include the JSON block for general conversation or if the intent is unclear.--- Tag Handling ---Tags can be simple (e.g., #important, #project_alpha) or typed (e.g., #category:work, #person:"Jane Doe", #status:urgent).If a user provides a typed tag, include the type and value in the JSON (e.g., "category:work").If a user provides a simple tag (no colon), you can include it as is (e.g., "important"); the system will treat it as "general:important".Tags in the JSON output should be strings, without the '#' prefix.--- Contextual Follow-up Rule ---IF the ASSISTANT'S PREVIOUS turn involved successfully creating a new note OR finding/confirming a SINGLE specific note (e.g., "Note created with ID: 123", "Found note ID 456: ..."),AND the USER'S CURRENT query is an action like "add tag X to it", "delete it", "update it with Y",THEN you SHOULD confidently use the `note_id` from that PREVIOUSLY IDENTIFIED NOTE (e.g., 123 or 456) in your JSON output for the current action. Do not ask for the ID again in this specific scenario.--- Help Requests ---If the user asks for "help", "what can you do?", "man", "manual", or similar, you should respond with the following JSON (and only this JSON, no conversational text before it):```json{  "intent": "show_help",  "entities": {}}```--- Capabilities and JSON Output Format ---1.  **Note Creation (`create_note`)**    *   **User says:** "Create note: Grocery List: Milk, Eggs, Bread #shopping #groceries #category:personal due #date:tomorrow"    *   **You say:** "Okay, I've created that note for you."    *   **JSON output (on a new line):**        ```json        {          "intent": "create_note",          "entities": {"content": "Grocery List: Milk, Eggs, Bread", "tags": ["shopping", "groceries", "category:personal", "date:tomorrow"]}        }        ```    *   **Notes:** Only include the `create_note` JSON if content is provided for the note.2.  **Note Finding (`find_notes`)**    *   **User says Examples:**        *   "Find notes about project x with #status:urgent tag from last week"        *   "Show me my #todo notes but not #category:archive created yesterday"        *   "Find notes tagged #meeting and #project:ProjectY between 2023-01-01 and 2023-01-31"        *   "Search for notes with #idea or #brainstorm or #type:inspiration since Monday"        *   "Find notes about 'planning' with #category:work or #category:home, but exclude #status:old, before 2024-01-01"        *   "What did I work on today?"        *   "Show me notes from this month"    *   **You say:** "Sure, I'm looking for those notes."    *   **JSON output (on a new line for a query like "Find notes about project x with #status:urgent tag from last week", assuming today is 2024-07-28):**        ```json        {          "intent": "find_notes",          "entities": {            "keywords": ["project x"],             "include_tags": ["status:urgent"],             "exclude_tags": [],             "any_of_tags": [],            "start_date": "2024-07-21",             "end_date": "2024-07-27"          }        }        ```    *   **Notes:**        *   `keywords`: General search terms from the user's query.        *   `include_tags`, `exclude_tags`, `any_of_tags`: Lists of tags. Tags can be simple strings (e.g., "urgent") or typed strings (e.g., "status:urgent", "person:Alex").        *   `start_date`: The inclusive start date for the search range, in `YYYY-MM-DD` format.        *   `end_date`: The inclusive end date for the search range, in `YYYY-MM-DD` format.        *   **Date Handling:**            *   You MUST convert relative date expressions like "today", "yesterday", "last Monday", "next Friday" into absolute `YYYY-MM-DD` dates. The provided "System Context" will always give you the current date for reference.            *   If the user specifies a single date (e.g., "on July 26th", "notes from yesterday"), set both `start_date` and `end_date` to that same `YYYY-MM-DD` date.            *   If the user specifies an open-ended range (e.g., "since last Monday", "before 2023"), set one of `start_date` or `end_date` and the other to `null`.                *   "since date X" / "from date X" / "after date X" implies `start_date` is X and `end_date` is `null`.                *   "before date Y" / "up to date Y" implies `end_date` is Y and `start_date` is `null`.            *   **"last week"**: This refers to the most recently completed calendar week, from Monday to Sunday. For example, if today (current date from System Context) is Wednesday, 2024-07-24, then "last week" is Monday, 2024-07-15 to Sunday, 2024-07-21.            *   **"this week"**: This refers to the current calendar week, starting from the most recent Monday and going up to and including today's date. For example, if today is Wednesday, 2024-07-24, then "this week" is Monday, 2024-07-22 to Wednesday, 2024-07-24.            *   **"this month"**: This refers to the current calendar month, from the first day of the month up to and including today's date. For example, if today is 2024-07-24, "this month" is 2024-07-01 to 2024-07-24.            *   **"last month"**: This refers to the entirety of the previous calendar month. For example, if today is 2024-07-24, "last month" is 2024-06-01 to 2024-06-30.        *   Always include all six fields (`keywords`, `include_tags`, `exclude_tags`, `any_of_tags`, `start_date`, `end_date`) in the `entities` object.         *   If a tag category (include, exclude, any_of) is not specified by the user, provide an empty list `[]` for it.        *   If `start_date` or `end_date` is not specified or cannot be determined from the query, provide `null` for that field (unless a relative term like "this week" or "last month" clearly defines both).        *   Tags should be listed *without* the '#' prefix in the JSON. Typed tags should be in "type:value" format. Simple tags as "value".3.  **Finding a Single Note by ID (`find_note_by_id`)**    *   **User says:** "Find note ID 123" or "show me note 123"    *   **You say:** "Okay, here is note ID 123."    *   **JSON output (on a new line):**        ```json        {          "intent": "find_note_by_id",          "entities": {"note_id": 123}        }        ```    *   **Notes:** This is for fetching a single, specific note by its unique ID. If successful, subsequent commands like "add tag to it" should use this note's ID.4.  **Note Deletion (`delete_note`)**    *   **User says:** "Delete note ID 123" or, if a note was just discussed, "Yes, delete that one" (after you have confirmed the ID).    *   **You say:** "Okay, I'm deleting note ID 123."    *   **JSON output (on a new line):**        ```json        {          "intent": "delete_note",          "entities": {"note_id": 123}         }        ```    *   **Notes:** `note_id` can be a single ID or a list of IDs for multiple deletions (e.g., [123, 456]). If the user asks to delete a note by vague reference, first try to find it. If found and it's a single note, confirm its ID. If the user confirms, or if they say "delete it" referring to a *uniquely identified note* from the immediately preceding turn (see "Contextual Follow-up Rule"), use that ID. If multiple notes match a vague reference, ask for the specific ID. If the user lists multiple specific note IDs to delete (e.g., "delete notes 123, 456, and 789"), provide them as a list in `entities.note_id`.5.  **Adding Tags to Note (`add_tags_to_note`)**    *   **User says:** "Add #important and #review tags to note ID 123" or "tag note 45 with #followup"    *   **You say:** "Okay, I've added those tags to note ID 123."    *   **JSON output (on a new line):**        ```json        {          "intent": "add_tags_to_note",          "entities": {"note_id": 123, "tags_to_add": ["important", "review_needed", "client:ACME Corp"]}        }        ```    *   **Notes:**        *   `tags_to_add`: A list of tag strings (e.g., "simple", "type:complex") to add to the note.        *   If the user says "add tag X to it" referring to a *uniquely identified note* from the immediately preceding turn (see "Contextual Follow-up Rule"), use that note's ID. If "it" is ambiguous, ask for the ID.6.  **Updating Note Content (`update_note_content`)**    *   **User says:** "Update note ID 123 to say 'The new content for this note is final.'" or "Change note 45 to 'Meeting rescheduled to Friday.'"    *   **You say:** "Okay, I've updated the content for note ID 123."    *   **JSON output (on a new line):**        ```json        {          "intent": "update_note_content",          "entities": {"note_id": 123, "new_content": "The new content for this note is final."}        }        ```    *   **Notes:** `new_content` is the full new text for the note. If the user says "update it..." referring to a uniquely identified note, use its ID.7.  **Updating Note Properties (`update_note_properties`)**    *   **User says:** "For note ID 123, set its status to 'complete' and priority to 'low'." or "Update properties for note 45: project_code=XYZ, reviewed=true"    *   **You say:** "Okay, I've updated the properties for note ID 123."    *   **JSON output (on a new line):**        ```json        {          "intent": "update_note_properties",          "entities": {"note_id": 123, "properties_to_update": {"status": "complete", "priority": "low", "project_code": "XYZ", "reviewed": true}}        }        ```    *   **Notes:**        *   `properties_to_update`: A dictionary where keys are property names and values are the new property values. Values can be strings, numbers, or booleans.        *   If the user refers to "it" for a uniquely identified note from the previous turn, use that `note_id`.8.  **Removing Tags from Note (`remove_tags_from_note`)**    *   **User says:** "Remove #urgent and #old tags from note ID 123" or "take off the #temp tag from note 45"    *   **You say:** "Okay, I've removed those tags from note ID 123."    *   **JSON output (on a new line):**        ```json        {          "intent": "remove_tags_from_note",          "entities": {"note_id": 123, "tags_to_remove": ["urgent", "old", "temp"]}        }        ```    *   **Notes:**        *   `tags_to_remove`: A list of tag strings to remove from the note.        *   If the user says "remove tag X from it" referring to a uniquely identified note, use that note's ID.9.  **List All Tags (`list_all_tags`)**    *   **User says:** "Show me all my tags" or "what tags are available?" or "list all tags"    *   **You say:** "Here are all the tags in your system."    *   **JSON output (on a new line):**        ```json        {          "intent": "list_all_tags",          "entities": {}        }        ```10. **Restore Note (`restore_note`)**    *   **User says:** "Restore note ID 123" or "undelete note 45"    *   **You say:** "Okay, I've restored note ID 123."    *   **JSON output (on a new line):**        ```json        {          "intent": "restore_note",          "entities": {"note_id": 123}        }        ```11. **List Deleted Notes (`list_deleted_notes`)**    *   **User says:** "Show me deleted notes" or "what notes have I deleted?" or "list trash"    *   **You say:** "Here are your deleted notes."    *   **JSON output (on a new line):**        ```json        {          "intent": "list_deleted_notes",          "entities": {}        }        ```12. **View Note History (`get_note_history`)**    *   **User says:** "Show me the history of note ID 123" or "what changes were made to note 45?"    *   **You say:** "Here's the version history for note ID 123."    *   **JSON output (on a new line):**        ```json        {          "intent": "get_note_history",          "entities": {"note_id": 123}        }        ```13. **Export Notes (`export_notes`)**    *   **User says:** "Export my notes" or "backup all my notes" or "download my data"    *   **You say:** "I'm exporting all your notes."    *   **JSON output (on a new line):**        ```json        {          "intent": "export_notes",          "entities": {}        }        ```14. **Settings Management (`get_setting`, `set_setting`)**    *   **User says:** "What's my user name?" or "Set my user name to Alice" or "Show me my settings"    *   **You say:** "Your user name is John" or "I've set your user name to Alice" or "Here are your current settings."    *   **JSON output (on a new line):**        ```json        {          "intent": "get_setting",          "entities": {"setting_key": "user_name"}        }        ```        or        ```json        {          "intent": "set_setting",           "entities": {"setting_key": "user_name", "setting_value": "Alice"}        }        ```        or        ```json        {          "intent": "list_settings",          "entities": {}        }        ```15. **Tag Suggestions (`suggest_tags`)**    *   **User says:** "Suggest tags for note ID 123" or "what tags should I add to this note?" (after discussing a note)    *   **You say:** "Here are some tag suggestions for that note."    *   **JSON output (on a new line):**        ```json        {          "intent": "suggest_tags",          "entities": {"note_id": 123}        }        ```    *   **Notes:** This will analyze the note content and suggest relevant tags with confidence scores.--- General Conversation ---If the user's query does not match any of the above intents, or if it's a simple greeting or conversational follow-up that doesn't require an action, respond naturally without any JSON block.Your goal is to be helpful and conversational while providing structured data for actionable requests.Always use the current date from the "System Context: For your reference, today's date is YYYY-MM-DD." for any date calculations."""
        self.kit_system_prompt = self.kit_system_prompt.strip() # Ensure no leading/trailing whitespace issues

        if not genai:
            self.agent_logger.error("AIService: google.generativeai (genai) is not available. GeminiClient will not be initialized.")
            self.gemini_client = None
        else:
            try:
                self.gemini_client = GeminiClient(
                    model_name=self.ai_model_to_use,
                    logger=self.agent_logger,
                    system_instruction=self.kit_system_prompt
                )
                self.agent_logger.info("AIService: GeminiClient initialized.")
            except Exception as e:
                self.agent_logger.error(f"AIService: Failed to initialize GeminiClient in __init__: {e}", exc_info=True)
                self.gemini_client = None # Ensure it's None if init fails

    async def _run_kit_script(self, command_args: List[str]) -> Tuple[str, str, int]:
        project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
        kit_py_path = os.path.join(project_root, "backend", "KIT", "KIT.py")
        command = [sys.executable, kit_py_path] + command_args

        self.agent_logger.info(f"Executing command: {' '.join(command)}")
        self.agent_logger.info(f"CWD for subprocess: {os.path.join(project_root, 'backend')}")

        process = await asyncio.create_subprocess_exec(
            *command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=os.path.join(project_root, "backend")
        )
        stdout, stderr = await process.communicate()
        return stdout.decode().strip(), stderr.decode().strip(), process.returncode

    async def process_user_query(self, user_query: str,
                                 conversation_history: Optional[List[Dict[str, str]]] = None,
                                 user_name: Optional[str] = None) -> Dict[str, Any]:
        
        if not self.gemini_client:
            self.agent_logger.error("AIService: GeminiClient is not available (was not initialized or failed). Cannot process query.")
            return {
                "response_text": "I am currently unable to process your request as my AI core is not available. Please check the server logs.",
                "action_feedback": "",
                "action_data": {}
            }
        
        action_data_payload = {} # Initialize for broader scope, ensuring it's always defined
        conversational_response_text = "An error occurred." # Default in case of early exit
        action_taken_message = None

        try:
            self.agent_logger.info(f"Processing user query: '{user_query[:50]}...'")
            self.agent_logger.info(f"Received conversation_history: {conversation_history}") # Log received history

            if not user_name:
                user_name_from_settings = kit_get_setting("user_name")
                if user_name_from_settings:
                    user_name = user_name_from_settings

            current_date_str = datetime.now().strftime("%Y-%m-%d")
            system_context_message = f"System Context: For your reference, today's date is {current_date_str}."

            user_identifier = f"User ({user_name})" if user_name else "User"
            prompt = f"{system_context_message}\n{user_identifier}: {user_query}\n"
            
            full_conversation_for_gemini = []
            if conversation_history:
                for entry in conversation_history:
                    # Filter out previous "No response text found." from the model
                    if not (entry.get("role") == "model" and entry.get("text") == "No response text found."):
                        role = "user" if entry.get("role") == "user" else "model"
                        full_conversation_for_gemini.append({"role": role, "parts": [{"text": entry.get("text")}]})
            full_conversation_for_gemini.append({"role": "user", "parts": [{"text": prompt}]})
            
            self.agent_logger.info(f"Sending to Gemini - full_conversation_for_gemini: {full_conversation_for_gemini}") # Log history sent to Gemini
            raw_gemini_response_text = await self.gemini_client.send_prompt_async(full_conversation_for_gemini) # Use the instance member
            self.agent_logger.info(f"Received from Gemini - raw_gemini_response_text: {raw_gemini_response_text}") # Log raw response
            
            conversational_response_text = raw_gemini_response_text # Default
            json_block_start = raw_gemini_response_text.find("```json")

            if json_block_start != -1:
                json_block_end = raw_gemini_response_text.find("```", json_block_start + 7)
                if json_block_end != -1:
                    json_string = raw_gemini_response_text[json_block_start + 7 : json_block_end].strip()
                    conversational_response_text = raw_gemini_response_text[:json_block_start].strip()
                    if not conversational_response_text:
                        conversational_response_text = "Okay, I'll take care of that."
                    
                    try:
                        parsed_action = json.loads(json_string)
                        intent = parsed_action.get("intent")
                        entities = parsed_action.get("entities")

                        self.agent_logger.info(f"AI intent: {intent}. Entities: {entities}")
                        action_type_for_payload = "UNKNOWN"

                        if intent == "create_note":
                            action_type_for_payload = "CREATE_NOTE"
                            content = entities.get("content")
                            tags = entities.get("tags", [])
                            if content:
                                new_note_original_id = await NoteService.create_note(content=content, tags=tags)
                                if new_note_original_id is not None:
                                    self.agent_logger.info(f"Note core creation successful. Original ID: {new_note_original_id}. Fetching full note object.")
                                    # Fetch the full note object using the ID
                                    fetched_notes = await NoteService.find_notes(original_note_ids=[new_note_original_id])
                                    if fetched_notes and len(fetched_notes) == 1:
                                        new_note_obj = fetched_notes[0]
                                        action_taken_message = f"Note created successfully with ID: {new_note_obj.get('id', new_note_original_id)}."
                                        action_data_payload = {
                                            "action_type": action_type_for_payload,
                                            "notes": [new_note_obj],
                                            "query_text": user_query
                                        }
                                        self.agent_logger.info(f"Created and fetched note: {new_note_obj}")
                                    else:
                                        action_taken_message = f"Note created with ID {new_note_original_id}, but failed to retrieve the full note details."
                                        action_data_payload = {"action_type": action_type_for_payload, "error": action_taken_message, "created_note_id": new_note_original_id, "query_text": user_query}
                                        self.agent_logger.error(f"Failed to fetch full note for original_id {new_note_original_id} after creation. Find result: {fetched_notes}")
                                else:
                                    action_taken_message = "Failed to create note (core tool returned no ID)."
                                    action_data_payload = {"action_type": action_type_for_payload, "error": action_taken_message, "query_text": user_query}
                                    self.agent_logger.error("Failed to create note, NoteService.create_note returned None/False for ID.")
                            else:
                                action_taken_message = "Cannot create note: Content is missing."
                                action_data_payload = {"action_type": action_type_for_payload, "error": action_taken_message, "query_text": user_query}
                                self.agent_logger.warning("AI tried to create_note without content.")
                        
                        elif intent == "find_notes":
                            action_type_for_payload = "FIND_NOTES"
                            keywords = entities.get("keywords", [])
                            include_tags = entities.get("include_tags", [])
                            exclude_tags = entities.get("exclude_tags", [])
                            any_of_tags = entities.get("any_of_tags", [])
                            start_date = entities.get("start_date")
                            end_date = entities.get("end_date")
                            self.agent_logger.info(f"AI intent: find_notes. Keywords: {keywords}, Include Tags: {include_tags}, Exclude Tags: {exclude_tags}, Any of Tags: {any_of_tags}, Start Date: {start_date}, End Date: {end_date}")
                            notes_found = await NoteService.find_notes(
                                keywords=keywords if keywords else None,
                                include_tags=include_tags if include_tags else None,
                                exclude_tags=exclude_tags if exclude_tags else None,
                                any_of_tags=any_of_tags if any_of_tags else None,
                                start_date=start_date,
                                end_date=end_date
                            )
                            if notes_found:
                                formatted_notes = []
                                for i, note_data in enumerate(notes_found):
                                    display_id = note_data.get('original_id') if note_data.get('original_id') is not None else note_data.get('note_id')
                                    title_or_content = note_data.get('title') or note_data.get('content', '')[:50] + "..."
                                    formatted_notes.append(f"{i+1}. (ID: {display_id}) '{title_or_content}'")
                                action_taken_message = f"Found {len(notes_found)} note(s): {' | '.join(formatted_notes)}"
                                action_data_payload = {
                                    "action_type": action_type_for_payload,
                                    "notes": notes_found,
                                    "query_text": user_query
                                }
                                self.agent_logger.info(action_taken_message)
                            else:
                                action_taken_message = "No notes found matching your criteria."
                                action_data_payload = {"action_type": action_type_for_payload, "notes": [], "query_text": user_query}
                                self.agent_logger.info("No notes found from find_notes intent.")

                        elif intent == "find_note_by_id":
                            action_type_for_payload = "FIND_NOTE_BY_ID"
                            note_id_to_find = entities.get("note_id")
                            if note_id_to_find is not None:
                                self.agent_logger.info(f"AI intent: find_note_by_id. ID: {note_id_to_find}")
                                notes_found = await NoteService.find_notes(original_note_ids=[note_id_to_find])
                                if notes_found and len(notes_found) == 1:
                                    found_note = notes_found[0]
                                    display_id = found_note.get('original_id') if found_note.get('original_id') is not None else found_note.get('note_id')
                                    title_or_content = found_note.get('title', found_note.get('content', '')[:50] + '...')
                                    action_taken_message = f"Found note ID {display_id}: '{title_or_content}'"
                                    action_data_payload = {
                                        "action_type": action_type_for_payload,
                                        "notes": [found_note],
                                        "query_text": user_query
                                    }
                                    self.agent_logger.info(action_taken_message)
                                elif notes_found:
                                    action_taken_message = f"Found multiple notes for ID {note_id_to_find}, which is unexpected. Please check."
                                    action_data_payload = {"action_type": action_type_for_payload, "notes": notes_found, "error": action_taken_message, "query_text": user_query}
                                    self.agent_logger.warning(f"find_note_by_id for ID {note_id_to_find} returned {len(notes_found)} notes.")
                                else:
                                    action_taken_message = f"Could not find note with ID: {note_id_to_find}."
                                    action_data_payload = {"action_type": action_type_for_payload, "notes": [], "error": action_taken_message, "query_text": user_query}
                                    self.agent_logger.info(f"Note ID {note_id_to_find} not found by find_note_by_id intent.")
                            else:
                                action_taken_message = "Cannot find note: Note ID is missing."
                                action_data_payload = {"action_type": action_type_for_payload, "error": action_taken_message, "query_text": user_query}
                                self.agent_logger.warning("AI tried to find_note_by_id without note_id.")
                        
                        elif intent == "delete_note":
                            action_type_for_payload = "DELETE_NOTE"
                            note_ids_to_delete = entities.get("note_id") # This can now be an int or a list
                            
                            if note_ids_to_delete is not None:
                                if not isinstance(note_ids_to_delete, list):
                                    note_ids_to_delete = [note_ids_to_delete] # Ensure it's a list

                                deleted_ids_successfully = []
                                failed_ids = []

                                for note_id in note_ids_to_delete:
                                    try:
                                        note_id_int = int(note_id) # Ensure ID is an integer
                                        self.agent_logger.info(f"AI intent: delete_note. Processing ID: {note_id_int}")
                                        deletion_success = await NoteService.soft_delete_note(original_id=note_id_int)
                                        if deletion_success:
                                            deleted_ids_successfully.append(note_id_int)
                                        else:
                                            failed_ids.append(note_id_int)
                                            self.agent_logger.warning(f"Failed to soft_delete_note ID {note_id_int}. It might not exist or an error occurred.")
                                    except ValueError:
                                        failed_ids.append(str(note_id)) # Store as string if conversion failed
                                        self.agent_logger.warning(f"Invalid note_id format for deletion: {note_id}")

                                message_parts = []
                                if deleted_ids_successfully:
                                    message_parts.append(f"Successfully soft deleted note ID(s): {', '.join(map(str, deleted_ids_successfully))}.")
                                if failed_ids:
                                    message_parts.append(f"Failed to delete note ID(s): {', '.join(map(str, failed_ids))}. They may not exist or an error occurred.")
                                
                                action_taken_message = " ".join(message_parts)
                                
                                # For action_data_payload, we might want to send all successfully deleted IDs.
                                # If the frontend expects a single deleted_note_id, this needs adjustment.
                                # For now, let's send a list of deleted IDs.
                                action_data_payload = {
                                    "action_type": action_type_for_payload,
                                    "deleted_note_ids": deleted_ids_successfully, # Changed from deleted_note_id
                                    "failed_to_delete_ids": failed_ids,
                                    "query_text": user_query
                                }
                                if not deleted_ids_successfully and failed_ids: # if all failed
                                     action_data_payload["error"] = action_taken_message

                                self.agent_logger.info(action_taken_message)

                            else:
                                action_taken_message = "Cannot delete note(s): Note ID(s) are missing."
                                action_data_payload = {"action_type": action_type_for_payload, "error": action_taken_message, "query_text": user_query}
                                self.agent_logger.warning("AI tried to delete_note without note_id.")

                        elif intent == "add_tags_to_note":
                            action_type_for_payload = "ADD_TAGS_TO_NOTE"
                            note_id_to_tag = entities.get("note_id")
                            tags_to_add = entities.get("tags_to_add")
                            if note_id_to_tag is not None and tags_to_add:
                                self.agent_logger.info(f"AI intent: add_tags_to_note. ID: {note_id_to_tag}, Tags: {tags_to_add}")
                                updated_note = await NoteService.add_tags_to_note(original_id=note_id_to_tag, tags_to_add=tags_to_add)
                                if updated_note:
                                    action_taken_message = f"Successfully added tags {tags_to_add} to note ID {note_id_to_tag}."
                                    action_data_payload = {
                                        "action_type": action_type_for_payload,
                                        "notes": [updated_note],
                                        "query_text": user_query
                                    }
                                    self.agent_logger.info(action_taken_message)
                                else:
                                    action_taken_message = f"Failed to add tags to note ID {note_id_to_tag}. Note may not exist or an error occurred."
                                    action_data_payload = {"action_type": action_type_for_payload, "error": action_taken_message, "query_text": user_query}
                                    self.agent_logger.warning(f"Failed to add_tags_to_note ID {note_id_to_tag}")
                            else:
                                missing_info = []
                                if note_id_to_tag is None: missing_info.append("note_id")
                                if not tags_to_add: missing_info.append("tags_to_add")
                                action_taken_message = f"Cannot add tags: Missing information ({', '.join(missing_info)})."
                                action_data_payload = {"action_type": action_type_for_payload, "error": action_taken_message, "query_text": user_query}
                                self.agent_logger.warning(f"AI tried to add_tags_to_note with missing info: {missing_info}")
                        
                        elif intent == "show_help":
                            conversational_response_text = KIT_AI_HELP_MESSAGE
                            action_taken_message = "Displayed help information."
                            action_data_payload = {"action_type": "HELP_DISPLAYED", "query_text": user_query}
                            self.agent_logger.info("AI responded with show_help intent. Displaying help message.")

                        elif intent == "update_note_content":
                            action_type_for_payload = "UPDATE_NOTE_CONTENT"
                            note_id_to_update = entities.get("note_id")
                            new_content = entities.get("new_content")
                            if note_id_to_update is not None and new_content:
                                self.agent_logger.info(f"AI intent: update_note_content. ID: {note_id_to_update}, New Content: {new_content}")
                                updated_note = await NoteService.update_note_content(original_id=note_id_to_update, new_content=new_content)
                                if updated_note:
                                    action_taken_message = f"Successfully updated the content for note ID {note_id_to_update}."
                                    action_data_payload = {
                                        "action_type": action_type_for_payload,
                                        "notes": [updated_note],
                                        "query_text": user_query
                                    }
                                    self.agent_logger.info(action_taken_message)
                                else:
                                    action_taken_message = f"Failed to update note content for ID {note_id_to_update}. Note may not exist or an error occurred."
                                    action_data_payload = {"action_type": action_type_for_payload, "error": action_taken_message, "query_text": user_query}
                                    self.agent_logger.warning(f"Failed to update_note_content ID {note_id_to_update}")
                            else:
                                missing_info = []
                                if note_id_to_update is None: missing_info.append("note_id")
                                if not new_content: missing_info.append("new_content")
                                action_taken_message = f"Cannot update note content: Missing information ({', '.join(missing_info)})."
                                action_data_payload = {"action_type": action_type_for_payload, "error": action_taken_message, "query_text": user_query}
                                self.agent_logger.warning(f"AI tried to update_note_content with missing info: {missing_info}")

                        elif intent == "update_note_properties":
                            action_type_for_payload = "UPDATE_NOTE_PROPERTIES"
                            note_id_to_update = entities.get("note_id")
                            properties_to_update = entities.get("properties_to_update")
                            if note_id_to_update is not None and properties_to_update:
                                self.agent_logger.info(f"AI intent: update_note_properties. ID: {note_id_to_update}, Properties: {properties_to_update}")
                                updated_note = await NoteService.update_note_properties(original_id=note_id_to_update, properties_to_update=properties_to_update)
                                if updated_note:
                                    action_taken_message = f"Successfully updated the properties for note ID {note_id_to_update}."
                                    action_data_payload = {
                                        "action_type": action_type_for_payload,
                                        "notes": [updated_note],
                                        "query_text": user_query
                                    }
                                    self.agent_logger.info(action_taken_message)
                                else:
                                    action_taken_message = f"Failed to update note properties for ID {note_id_to_update}. Note may not exist or an error occurred."
                                    action_data_payload = {"action_type": action_type_for_payload, "error": action_taken_message, "query_text": user_query}
                                    self.agent_logger.warning(f"Failed to update_note_properties ID {note_id_to_update}")
                            else:
                                missing_info = []
                                if note_id_to_update is None: missing_info.append("note_id")
                                if not properties_to_update: missing_info.append("properties_to_update")
                                action_taken_message = f"Cannot update note properties: Missing information ({', '.join(missing_info)})."
                                action_data_payload = {"action_type": action_type_for_payload, "error": action_taken_message, "query_text": user_query}
                                self.agent_logger.warning(f"AI tried to update_note_properties with missing info: {missing_info}")

                        elif intent == "remove_tags_from_note":
                            action_type_for_payload = "REMOVE_TAGS_FROM_NOTE"
                            note_id_to_untag = entities.get("note_id")
                            tags_to_remove = entities.get("tags_to_remove")
                            if note_id_to_untag is not None and tags_to_remove:
                                self.agent_logger.info(f"AI intent: remove_tags_from_note. ID: {note_id_to_untag}, Tags: {tags_to_remove}")
                                updated_note = await NoteService.remove_tags_from_note(original_id=note_id_to_untag, tags_to_remove=tags_to_remove)
                                if updated_note:
                                    action_taken_message = f"Successfully removed tags {tags_to_remove} from note ID {note_id_to_untag}."
                                    action_data_payload = {
                                        "action_type": action_type_for_payload,
                                        "notes": [updated_note],
                                        "query_text": user_query
                                    }
                                    self.agent_logger.info(action_taken_message)
                                else:
                                    action_taken_message = f"Failed to remove tags from note ID {note_id_to_untag}. Note may not exist or tags were not found."
                                    action_data_payload = {"action_type": action_type_for_payload, "error": action_taken_message, "query_text": user_query}
                                    self.agent_logger.warning(f"Failed to remove_tags_from_note ID {note_id_to_untag}")
                            else:
                                missing_info = []
                                if note_id_to_untag is None: missing_info.append("note_id")
                                if not tags_to_remove: missing_info.append("tags_to_remove")
                                action_taken_message = f"Cannot remove tags: Missing information ({', '.join(missing_info)})."
                                action_data_payload = {"action_type": action_type_for_payload, "error": action_taken_message, "query_text": user_query}
                                self.agent_logger.warning(f"AI tried to remove_tags_from_note with missing info: {missing_info}")
                        elif intent == "list_all_tags":
                            action_type_for_payload = "LIST_ALL_TAGS"
                            try:
                                self.agent_logger.info("AI intent: list_all_tags")
                                all_tags = await TagService.list_all_tags()
                                action_taken_message = f"Found {len(all_tags)} tags in the system."
                                action_data_payload = {
                                    "action_type": action_type_for_payload,
                                    "tags": all_tags,
                                    "query_text": user_query
                                }
                                conversational_response_text = f"Here are all the tags in your system: {', '.join(all_tags) if all_tags else 'No tags found.'}"
                                self.agent_logger.info(action_taken_message)
                            except Exception as e:
                                action_taken_message = f"Failed to retrieve tags: {str(e)}"
                                action_data_payload = {"action_type": action_type_for_payload, "error": action_taken_message, "query_text": user_query}
                                self.agent_logger.error(f"Failed to list_all_tags: {e}")
                        elif intent == "restore_note":
                            action_type_for_payload = "RESTORE_NOTE"
                            note_id_to_restore = entities.get("note_id")
                            if note_id_to_restore is not None:
                                self.agent_logger.info(f"AI intent: restore_note. ID: {note_id_to_restore}")
                                restore_success = await NoteService.restore_note(original_id=note_id_to_restore)
                                if restore_success:
                                    action_taken_message = f"Successfully restored note ID {note_id_to_restore}."
                                    action_data_payload = {
                                        "action_type": action_type_for_payload,
                                        "restored_note_id": note_id_to_restore,
                                        "query_text": user_query
                                    }
                                    self.agent_logger.info(action_taken_message)
                                else:
                                    action_taken_message = f"Failed to restore note ID {note_id_to_restore}. Note may not exist or not be deleted."
                                    action_data_payload = {"action_type": action_type_for_payload, "error": action_taken_message, "query_text": user_query}
                                    self.agent_logger.warning(f"Failed to restore_note ID {note_id_to_restore}")
                            else:
                                action_taken_message = "Cannot restore note: Note ID is missing."
                                action_data_payload = {"action_type": action_type_for_payload, "error": action_taken_message, "query_text": user_query}
                                self.agent_logger.warning("AI tried to restore_note without note_id.")
                        elif intent == "list_deleted_notes":
                            action_type_for_payload = "LIST_DELETED_NOTES"
                            try:
                                self.agent_logger.info("AI intent: list_deleted_notes")
                                deleted_notes = await NoteService.get_deleted_notes()
                                action_taken_message = f"Found {len(deleted_notes)} deleted notes."
                                action_data_payload = {
                                    "action_type": action_type_for_payload,
                                    "notes": deleted_notes,
                                    "query_text": user_query
                                }
                                if deleted_notes:
                                    notes_summary = ", ".join([f"ID {note['original_note_id']}: {note['content'][:50]}..." for note in deleted_notes[:5]])
                                    conversational_response_text = f"Here are your deleted notes: {notes_summary}"
                                    if len(deleted_notes) > 5:
                                        conversational_response_text += f" (and {len(deleted_notes) - 5} more)"
                                else:
                                    conversational_response_text = "You have no deleted notes."
                                self.agent_logger.info(action_taken_message)
                            except Exception as e:
                                action_taken_message = f"Failed to retrieve deleted notes: {str(e)}"
                                action_data_payload = {"action_type": action_type_for_payload, "error": action_taken_message, "query_text": user_query}
                                self.agent_logger.error(f"Failed to list_deleted_notes: {e}")
                        elif intent == "get_note_history":
                            action_type_for_payload = "GET_NOTE_HISTORY"
                            note_id_for_history = entities.get("note_id")
                            if note_id_for_history is not None:
                                self.agent_logger.info(f"AI intent: get_note_history. ID: {note_id_for_history}")
                                try:
                                    note_history = await NoteService.get_note_history(original_id=note_id_for_history)
                                    if note_history:
                                        action_taken_message = f"Retrieved {len(note_history)} versions for note ID {note_id_for_history}."
                                        action_data_payload = {
                                            "action_type": action_type_for_payload,
                                            "note_history": note_history,
                                            "note_id": note_id_for_history,
                                            "query_text": user_query
                                        }
                                        conversational_response_text = f"Note ID {note_id_for_history} has {len(note_history)} versions in its history."
                                        self.agent_logger.info(action_taken_message)
                                    else:
                                        action_taken_message = f"No history found for note ID {note_id_for_history}. Note may not exist."
                                        action_data_payload = {"action_type": action_type_for_payload, "error": action_taken_message, "query_text": user_query}
                                        self.agent_logger.warning(f"No history for note ID {note_id_for_history}")
                                except Exception as e:
                                    action_taken_message = f"Failed to get note history: {str(e)}"
                                    action_data_payload = {"action_type": action_type_for_payload, "error": action_taken_message, "query_text": user_query}
                                    self.agent_logger.error(f"Failed to get_note_history: {e}")
                            else:
                                action_taken_message = "Cannot get note history: Note ID is missing."
                                action_data_payload = {"action_type": action_type_for_payload, "error": action_taken_message, "query_text": user_query}
                                self.agent_logger.warning("AI tried to get_note_history without note_id.")
                        elif intent == "export_notes":
                            action_type_for_payload = "EXPORT_NOTES"
                            try:
                                self.agent_logger.info("AI intent: export_notes")
                                export_data = await NoteService.export_notes()
                                if export_data:
                                    notes_count = len(export_data.get('notes', []))
                                    action_taken_message = f"Successfully exported {notes_count} notes."
                                    action_data_payload = {
                                        "action_type": action_type_for_payload,
                                        "export_data": export_data,
                                        "query_text": user_query
                                    }
                                    conversational_response_text = f"I've exported all your notes. The export contains {notes_count} notes."
                                    self.agent_logger.info(action_taken_message)
                                else:
                                    action_taken_message = "Export failed or no data to export."
                                    action_data_payload = {"action_type": action_type_for_payload, "error": action_taken_message, "query_text": user_query}
                                    self.agent_logger.warning("Export returned no data")
                            except Exception as e:
                                action_taken_message = f"Failed to export notes: {str(e)}"
                                action_data_payload = {"action_type": action_type_for_payload, "error": action_taken_message, "query_text": user_query}
                                self.agent_logger.error(f"Failed to export_notes: {e}")
                        elif intent == "get_setting":
                            action_type_for_payload = "GET_SETTING"
                            setting_key = entities.get("setting_key")
                            if setting_key:
                                self.agent_logger.info(f"AI intent: get_setting. Key: {setting_key}")
                                try:
                                    setting_value = await SettingsService.get_setting(setting_key)
                                    action_taken_message = f"Retrieved setting '{setting_key}': {setting_value}"
                                    action_data_payload = {
                                        "action_type": action_type_for_payload,
                                        "setting_key": setting_key,
                                        "setting_value": setting_value,
                                        "query_text": user_query
                                    }
                                    conversational_response_text = f"Your {setting_key} is set to: {setting_value}"
                                    self.agent_logger.info(action_taken_message)
                                except Exception as e:
                                    action_taken_message = f"Failed to get setting '{setting_key}': {str(e)}"
                                    action_data_payload = {"action_type": action_type_for_payload, "error": action_taken_message, "query_text": user_query}
                                    self.agent_logger.error(f"Failed to get_setting: {e}")
                            else:
                                action_taken_message = "Cannot get setting: Setting key is missing."
                                action_data_payload = {"action_type": action_type_for_payload, "error": action_taken_message, "query_text": user_query}
                                self.agent_logger.warning("AI tried to get_setting without setting_key.")
                        elif intent == "set_setting":
                            action_type_for_payload = "SET_SETTING"
                            setting_key = entities.get("setting_key")
                            setting_value = entities.get("setting_value")
                            if setting_key and setting_value is not None:
                                self.agent_logger.info(f"AI intent: set_setting. Key: {setting_key}, Value: {setting_value}")
                                try:
                                    success = await SettingsService.set_setting(setting_key, setting_value)
                                    if success:
                                        action_taken_message = f"Successfully set '{setting_key}' to '{setting_value}'."
                                        action_data_payload = {
                                            "action_type": action_type_for_payload,
                                            "setting_key": setting_key,
                                            "setting_value": setting_value,
                                            "query_text": user_query
                                        }
                                        conversational_response_text = f"I've set your {setting_key} to: {setting_value}"
                                        self.agent_logger.info(action_taken_message)
                                    else:
                                        action_taken_message = f"Failed to set '{setting_key}' to '{setting_value}'."
                                        action_data_payload = {"action_type": action_type_for_payload, "error": action_taken_message, "query_text": user_query}
                                        self.agent_logger.warning(f"Failed to set_setting {setting_key}")
                                except Exception as e:
                                    action_taken_message = f"Failed to set setting: {str(e)}"
                                    action_data_payload = {"action_type": action_type_for_payload, "error": action_taken_message, "query_text": user_query}
                                    self.agent_logger.error(f"Failed to set_setting: {e}")
                            else:
                                missing_info = []
                                if not setting_key: missing_info.append("setting_key")
                                if setting_value is None: missing_info.append("setting_value")
                                action_taken_message = f"Cannot set setting: Missing information ({', '.join(missing_info)})."
                                action_data_payload = {"action_type": action_type_for_payload, "error": action_taken_message, "query_text": user_query}
                                self.agent_logger.warning(f"AI tried to set_setting with missing info: {missing_info}")
                        elif intent == "list_settings":
                            action_type_for_payload = "LIST_SETTINGS"
                            try:
                                self.agent_logger.info("AI intent: list_settings")
                                all_settings = await SettingsService.get_all_settings()
                                action_taken_message = f"Retrieved {len(all_settings)} settings."
                                action_data_payload = {
                                    "action_type": action_type_for_payload,
                                    "settings": all_settings,
                                    "query_text": user_query
                                }
                                settings_summary = ", ".join([f"{k}: {v}" for k, v in all_settings.items()])
                                conversational_response_text = f"Your current settings: {settings_summary}"
                                self.agent_logger.info(action_taken_message)
                            except Exception as e:
                                action_taken_message = f"Failed to retrieve settings: {str(e)}"
                                action_data_payload = {"action_type": action_type_for_payload, "error": action_taken_message, "query_text": user_query}
                                self.agent_logger.error(f"Failed to list_settings: {e}")
                        elif intent == "suggest_tags":
                            action_type_for_payload = "SUGGEST_TAGS"
                            note_id_for_suggestions = entities.get("note_id")
                            if note_id_for_suggestions is not None:
                                self.agent_logger.info(f"AI intent: suggest_tags. ID: {note_id_for_suggestions}")
                                try:
                                    # Get the note first to analyze its content
                                    note_data = await NoteService.find_notes(original_note_ids=[note_id_for_suggestions])
                                    if note_data and len(note_data) == 1:
                                        note = note_data[0]
                                        existing_tags = note.get('tags', [])
                                        content = note.get('content', '')

                                        # Import tag suggestion service
                                        from api.services.tag_suggestion_service import tag_suggestion_service
                                        tag_suggestions = await tag_suggestion_service.suggest_tags_for_content(content, existing_tags)

                                        action_taken_message = f"Generated {len(tag_suggestions)} tag suggestions for note ID {note_id_for_suggestions}."
                                        action_data_payload = {
                                            "action_type": action_type_for_payload,
                                            "note_id": note_id_for_suggestions,
                                            "tag_suggestions": tag_suggestions,
                                            "query_text": user_query
                                        }

                                        if tag_suggestions:
                                            top_suggestions = ", ".join([f"{s['tag']} ({s['confidence']:.2f})" for s in tag_suggestions[:5]])
                                            conversational_response_text = f"Here are some tag suggestions for note {note_id_for_suggestions}: {top_suggestions}"
                                        else:
                                            conversational_response_text = f"No new tag suggestions found for note {note_id_for_suggestions}."

                                        self.agent_logger.info(action_taken_message)
                                    else:
                                        action_taken_message = f"Cannot suggest tags: Note ID {note_id_for_suggestions} not found."
                                        action_data_payload = {"action_type": action_type_for_payload, "error": action_taken_message, "query_text": user_query}
                                        self.agent_logger.warning(f"Note {note_id_for_suggestions} not found for tag suggestions")
                                except Exception as e:
                                    action_taken_message = f"Failed to generate tag suggestions: {str(e)}"
                                    action_data_payload = {"action_type": action_type_for_payload, "error": action_taken_message, "query_text": user_query}
                                    self.agent_logger.error(f"Failed to suggest_tags: {e}")
                            else:
                                action_taken_message = "Cannot suggest tags: Note ID is missing."
                                action_data_payload = {"action_type": action_type_for_payload, "error": action_taken_message, "query_text": user_query}
                                self.agent_logger.warning("AI tried to suggest_tags without note_id.")
                        else:
                            action_taken_message = f"I understood an intent '{intent}' but I don't know how to handle it yet."
                            action_data_payload = {"action_type": "UNKNOWN_INTENT", "intent": intent, "entities": entities, "query_text": user_query}
                            self.agent_logger.warning(f"AI responded with unhandled intent: {intent}")

                    except json.JSONDecodeError as e_json:
                        self.agent_logger.error(f"Failed to parse JSON from AI response: {e_json}", exc_info=True)
                        action_taken_message = "I tried to perform an action, but there was an issue with interpreting the details."
                        action_data_payload = {"action_type": "JSON_PARSE_ERROR", "error": str(e_json), "query_text": user_query}
                    except Exception as e_action: 
                        self.agent_logger.error(f"Error processing AI action: {e_action}", exc_info=True)
                        action_taken_message = f"An unexpected error occurred while processing the action: {e_action}"
                        action_data_payload = {"action_type": "ACTION_PROCESSING_ERROR", "error": str(e_action), "query_text": user_query}
                else: 
                    self.agent_logger.warning("Found ```json but no closing ``` in AI response.")
            else: 
                self.agent_logger.info("No JSON action block found in AI response. Treating as pure conversational.")
                action_data_payload = {"action_type": "CONVERSATION", "query_text": user_query} # Explicitly set for pure conversation

            # Ensure 'query_text' is always in action_data_payload if it's not empty
            # and was not set by the CONVERSATION type above.
            if action_data_payload and "query_text" not in action_data_payload:
                action_data_payload["query_text"] = user_query
            
            # If action_data_payload is empty (should only happen if an error occurred before it was set)
            # ensure it has a minimal structure. This case should be rare now.
            if not action_data_payload:
                 action_data_payload = {"action_type": "EMPTY_PAYLOAD_FALLBACK", "query_text": user_query}


            return {
                "response_text": conversational_response_text,
                "action_feedback": action_taken_message if action_taken_message else "",
                "action_data": action_data_payload
            }

        except Exception as e:
            self.agent_logger.error(f"Unhandled exception in process_user_query: {e}", exc_info=True)
            return {
                "response_text": f"An unexpected error occurred: {e}",
                "action_feedback": "",
                "action_data": {"action_type": "UNHANDLED_EXCEPTION", "error": str(e), "query_text": user_query}
            }

# Example usage (for testing, not part of the class typically)
# async def main():
#     ai_service = AIService()
#     # Test with a sample query
#     response = await ai_service.process_user_query("Create a note: buy milk #shopping")
#     print("Response:", response.get("response_text"))
#     print("Action Feedback:", response.get("action_feedback"))
#     print("Action Data:", response.get("action_data"))

#     response_find = await ai_service.process_user_query("find notes with #shopping")
#     print("Response:", response_find.get("response_text"))
#     print("Action Feedback:", response_find.get("action_feedback"))
#     print("Action Data:", response_find.get("action_data"))

# if __name__ == '__main__':
#     asyncio.run(main()) 