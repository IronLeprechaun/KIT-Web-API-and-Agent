#!/usr/bin/env python3
# KIT.py - The Agent

import subprocess
import sys
import shlex # For safely splitting command strings
import os
import json # For parsing Gemini's response
import logging # Added for logging
from datetime import datetime, date # Added date for auto-purge
from collections import deque # Added for conversation history

# Determine the project root directory, assuming KIT.py is in KIT/
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.append(PROJECT_ROOT)
    KIT_DIR = os.path.dirname(os.path.abspath(__file__))
    if KIT_DIR not in sys.path:
        sys.path.append(KIT_DIR)

from gemini_client import get_gemini_response, GeminiClientError
from logger_utils import setup_kit_loggers

# Import necessary functions for auto-purge
from KITCore.tools.settings_tool import get_setting as tool_get_setting, set_setting as tool_set_setting
from KITCore.tools.note_tool import purge_deleted_notes as tool_purge_deleted_notes

agent_logger = None
trace_logger = None

MAX_HISTORY_TURNS = 5
KITCORE_EXEC_ERROR_RETURN_CODE = -999

def run_automatic_daily_purge():
    """Checks if an automatic daily purge is needed and runs it."""
    if agent_logger:
        agent_logger.info("Performing automatic daily purge check...")
    else:
        print("Performing automatic daily purge check...")

    today_str = date.today().isoformat()
    last_purge_date = tool_get_setting("last_auto_purge_date")

    if last_purge_date == today_str:
        msg = "Automatic daily purge already performed today."
        if agent_logger: agent_logger.info(msg)
        else: print(msg)
        return

    default_days_to_purge = tool_get_setting("default_purge_days")

    if default_days_to_purge is None:
        msg = "Automatic daily purge skipped: 'default_purge_days' setting is not configured."
        if agent_logger: agent_logger.info(msg)
        else: print(msg)
        return
    
    if not isinstance(default_days_to_purge, int) or default_days_to_purge < 0:
        msg = f"Automatic daily purge skipped: 'default_purge_days' setting ('{default_days_to_purge}') is invalid (must be a non-negative integer)."
        if agent_logger: agent_logger.warning(msg)
        else: print(msg, file=sys.stderr)
        return

    try:
        # agent_logger.info(f"Attempting automatic purge for notes older than {default_days_to_purge} days.")
        # The purge_deleted_notes function from note_tool will print its own success/failure/count messages to stdout/stderr.
        # We rely on those messages for user feedback for the purge itself.
        purged_count = tool_purge_deleted_notes(older_than_days=default_days_to_purge)
        
        if purged_count >= 0: # Assuming 0 or more is success, negative might be an error code if API changes
            msg = f"Automatic daily purge check: {purged_count} note lineage(s) older than {default_days_to_purge} days were purged."
            if agent_logger: agent_logger.info(msg)
            else: print(msg)
            # Update last purge date only if the operation was considered successful by the tool
            if not tool_set_setting("last_auto_purge_date", today_str):
                err_msg = "Critical: Automatic purge ran, but failed to update 'last_auto_purge_date' setting!"
                if agent_logger: agent_logger.error(err_msg)
                else: print(err_msg, file=sys.stderr)
        else:
            # This path might not be reachable if purge_deleted_notes always returns >= 0 or raises error
            msg = f"Automatic daily purge check: Purge operation reported an issue (returned {purged_count})."
            if agent_logger: agent_logger.warning(msg)
            else: print(msg, file=sys.stderr)

    except Exception as e:
        # Catch unexpected errors during the purge or setting update
        err_msg = f"Error during automatic daily purge: {e}"
        if agent_logger: agent_logger.error(err_msg, exc_info=True)
        else: print(err_msg, file=sys.stderr)

def get_kit_static_help_message() -> str:
    """Returns the static help message for KIT commands."""
    help_text = '''Here's what I can do:
  - **Create a new note:** `add --content \"<note_content>\" [--tags \"<tag1,tag2,...>\"] [--props '{{ \"key\":\"value\" }}']`
    Example: `add --content \"Buy milk\" --tags \"shopping,urgent\"`
  - **Find notes:** `find [--tags \"<tag1,tag2,...>\"] [--keywords \"<keyword1,keyword2,...>\"] [--start_date \"YYYY-MM-DD HH:MM:SS\"] [--end_date \"YYYY-MM-DD HH:MM:SS\"]`
    Example: `find --tags \"project_alpha\" --keywords \"report\"`
  - **Update an existing note (content, multiple tags, props):** `update --original_id <id> [--new_content \"<content>\"] [--new_tags \"<tags>\"] [--new_props '{{ \"key\":\"value\" }}']`
    Example: `update --original_id 123 --new_content \"Updated report details\" --new_tags \"project_alpha,done\"`
  - **Add a single tag to a note:** `add-tag --original_id <id> --tag \"<tag_name>\"`
    Example: `add-tag --original_id 123 --tag \"important\"`
  - **Remove a single tag from a note:** `remove-tag --original_id <id> --tag \"<tag_name>\"`
    Example: `remove-tag --original_id 123 --tag \"urgent\"`
  - **Show note history:** `history --original_id <id>`
    Example: `history --original_id 123`
  - **Delete a note (soft delete):** `soft-delete --original_id <id>`
    Example: `soft-delete --original_id 123`
  - **Restore a deleted note:** `restore --original_id <id>`
    Example: `restore --original_id 123`
  - **List deleted notes:** `list-deleted`
    Example: `list-deleted`
  - **List all tags:** `list-all-tags`
    Example: `list-all-tags`
  - **Permanently remove deleted notes:** `purge-deleted [--older-than-days <days>]`
    Example: `purge-deleted` (purges all soft-deleted notes)
    Example: `purge-deleted --older-than-days 30` (purges notes soft-deleted more than 30 days ago)
  - **Export all notes:** `export-notes --file \"<filepath.json>\"`
    Example: `export-notes --file \"my_notes_backup.json\"`
  - **Import notes from file:** `import-notes --file \"<filepath.json>\"` (Warning: Best used on a fresh database!)
    Example: `import-notes --file \"my_notes_backup.json\"`
  - **Initialize the database (usually not needed by user):** `initdb`'''
    return help_text

def get_gemini_master_prompt(user_name: str | None = None, conversation_history: deque = None) -> str:
    user_name_guidance = "If you knew the user\\'s name (e.g., User_Name), you would use it (e.g., 'Hello, User_Name!')."
    if user_name:
        user_name_guidance = f"The user\\'s name is '{user_name}'. When appropriate (like in a greeting), you should use their name. (e.g., 'Hello, {user_name}!)."

    history_block = ""
    if conversation_history:
        history_items = []
        for turn in conversation_history:
            role = "User" if turn["role"] == "user" else "Assistant"
            content_str = str(turn['content']).replace('"', '\\\\"') # Escaping for JSON within prompt
            history_items.append(f"{role}: {content_str}")
        if history_items:
            history_block = "CONVERSATION HISTORY (Use this for context on the current query):\\\\n" + "\\\\n".join(history_items) + "\\\\n\\\\n"

    prompt = f"""{history_block}You are an intelligent assistant interpreting commands for the KIT system. \\\\
The user will provide a natural language query. Your task is to understand the query, \\\\
considering the CONVERSATION HISTORY if provided, \\\\
and respond with a JSON object that specifies the action(s) to be taken by KITCore.py, or indicates a conversational interaction.

KITCore.py has the following CLI commands available:
- `add --content \\\\\"<note_content>\\\\\" [--tags \\\\\"<tag1,tag2,...>\\\\\"] [--props \'{{ \\\\\"key\\\\\":\\\\\"value\\\\\" }}\']`
- `find [--tags \\\\\"<tag1,tag2,...>\\\\\"] [--keywords \\\\\"<keyword1,keyword2,...>\\\\\"] [--start_date \\\\\"YYYY-MM-DD HH:MM:SS\\\\\"] [--end_date \\\\\"YYYY-MM-DD HH:MM:SS\\\\\"]` (IMPORTANT: `find` NEVER uses `original_id`. It searches across all notes that are NOT soft-deleted. It can also understand relative date expressions like "today", "yesterday", "last week", "this month", "last month", "last year" for date filtering. You must convert these to absolute YYYY-MM-DD HH:MM:SS dates.)
- `update --original_id <original_note_id_as_int> [--new_content \\\\\"<new_content>\\\\\"] [--new_tags \\\\\"<new_tags,...>\\\\\"] [--new_props \'{{ \\\\\"key\\\\\":\\\\\"new_value\\\\\" }}\']` (Use for changing content, multiple tags, or properties. For adding/removing single tags, prefer `add-tag` or `remove-tag`.)
- `add-tag --original_id <original_note_id_as_int> --tag \\\\\"<tag_to_add>\\\\\"` (Adds a single tag to a note.)
- `remove-tag --original_id <original_note_id_as_int> --tag \\\\\"<tag_to_remove>\\\\\"` (Removes a single tag from a note.)
- `history --original_id <original_note_id_as_int>`
- `soft-delete --original_id <original_note_id_as_int>` (Marks a note as deleted. It can be restored.)
- `restore --original_id <original_note_id_as_int>` (Restores a soft-deleted note.)
- `list-deleted` (Shows all notes that are currently soft-deleted.)
- `list-all-tags` (Lists all unique tags present in the system. Takes no arguments.)
- `purge-deleted [--older-than-days <days_as_int>]` (Permanently removes soft-deleted notes. If --older-than-days is specified, only purges notes deleted longer than that period. THIS IS IRREVERSIBLE.)
- `export-notes --file \\\\\"<filepath.json>\\\\\"` (Exports all notes, tags, and versions to a JSON file.)
- `import-notes --file \\\\\"<filepath.json>\\\\\"` (Imports notes from a JSON file. Best used on a fresh/empty database.)
- `initdb`

Your JSON response MUST have ONE of the following structures:

Structure 1: Single Action / Conversational Response
{{
  \\\\\"intent\\\\\": \\\\\"<INTENT_NAME>\\\\\",
  \\\\\"kit_core_command\\\\\": \\\\\"<command_name_or_null>\\\\\",
  \\\\\"parameters\\\\\": {{}},
  \\\\\"response_text\\\\\": \\\\\"<text_for_direct_reply_or_null>\\\\\",
  \\\\\"output_tone\\\\\": \\\\\"<suggested_tone>\\\\\" 
}}

Structure 2: Multiple Sequential Actions (Use when the user\\'s query clearly implies multiple distinct KITCore operations)
{{
  \\\\\"actions_list\\\\\": [
    {{
      \\\\\"intent\\\\\": \\\\\"<INTENT_NAME_ACTION_1>\\\\\",
      \\\\\"kit_core_command\\\\\": \\\\\"<command_name_action_1>\\\\\",
      \\\\\"parameters\\\\\": {{}} 
    }},
    {{
      \\\\\"intent\\\\\": \\\\\"<INTENT_NAME_ACTION_2>\\\\\",
      \\\\\"kit_core_command\\\\\": \\\\\"<command_name_action_2>\\\\\",
      \\\\\"parameters\\\\\": {{}} 
    }}
    // ... more actions if needed
  ],
  \\\\\"output_tone\\\\\": \\\\\"<suggested_overall_tone>\\\\\" 
}}

**Intent and Command Mapping (Applies to single actions or actions within `actions_list`):**
- If the query maps to a KITCore tool, set `intent` to the corresponding tool name (e.g., `find_notes`, `add_note`, `update_note`, `add_tag`, `remove_tag`, `soft_delete_note`, `restore_note`, `get_note_history`, `list_deleted_notes`, `list_all_tags`, `purge_deleted_notes`, `export_notes`, `import_notes`, `init_db`). Set `kit_core_command` to the CLI command name (e.g., `find`, `add`, `update`, `add-tag`, `list-all-tags`, etc.) and `parameters` appropriately. **IMPORTANT: The keys in the `parameters` JSON object MUST be the base parameter names (e.g., `tags`, `content`, `original_id`, `new_content`, `file`), NOT the CLI flags (e.g., do NOT use `--tags` as a key).** `response_text` (for single action structure) should be null.
  - For `find` intent: Use only `tags`, `keywords`, `start_date`, `end_date` as parameter keys. DO NOT use `original_id`.
    **Relative Date Handling for `find`:** (Assume current date is **{{{{current_date_iso_for_gemini_do_not_modify}}}}** for calculations)
    When the user uses relative date expressions (e.g., "yesterday", "today", "last Tuesday", "this morning", "last week", "this month", "last year") for `find` queries, you MUST convert these into absolute `YYYY-MM-DD HH:MM:SS` timestamps for `--start_date` and/or `--end_date`.
    - "today": Start of today to end of today.
    - "yesterday": Start of yesterday to end of yesterday.
    - "this morning": Start of today to 12:00 PM today.
    - "last week": Start of Monday of last week to end of Sunday of last week.
    - "this week": Start of Monday of this week to end of Sunday of this week.
    - "next week": Start of Monday of next week to end of Sunday of next week.
    - "this month": Start of the first day of this month to end of the last day of this month.
    - "last month": Start of the first day of last month to end of the last day of last month.
    - "last year": Start of Jan 1st of last year to end of Dec 31st of last year.
    - For specific days like "last Tuesday", calculate the date. If time is not specified, assume the whole day (00:00:00 to 23:59:59).
    - Always use the provided `{{{{current_date_iso_for_gemini_do_not_modify}}}}` as the reference for "now" when making these calculations.
  - For `update` intent: Use for changing `new_content`, or `new_props`. If changing tags, if the user wants to set a *list* of tags (potentially replacing all existing ones), use `update --new_tags \\\\\"<tag1,tag2>\\\\\"`. If the user wants to add or remove a *single* tag, prefer the `add-tag` or `remove-tag` commands.
  - For `add-tag` intent: Use when the user explicitly asks to add a single tag to a note. Requires `original_id` and `tag` (string for the tag to add) parameters.
  - For `remove-tag` intent: Use when the user explicitly asks to remove a single tag from a note. Requires `original_id` and `tag` (string for the tag to remove) parameters.
  - For `history`, `soft-delete`, `restore` intents: `original_id` (integer) is a required parameter.
  - For `list-all-tags` intent: This command takes no parameters.
  - For `purge-deleted` intent: `older-than-days` is an optional integer parameter.
  - For `export-notes` and `import-notes` intents: `file` (filepath string) is a required parameter.

- If the query is a simple greeting (e.g., "hi", "hello"), use Structure 1. Set `intent` to `CONVERSATIONAL_GREETING`, `kit_core_command` to null, and `response_text` to a suitable greeting. {user_name_guidance}
- If the query is a general question not answerable by KITCore tools (e.g., "what is the capital of France?"), use Structure 1. Set `intent` to `GENERAL_QUERY`, `kit_core_command` to null, and `response_text` to "I can only help with managing notes using KITCore tools. I can\\'t answer general knowledge questions."
- If the query asks for help about KIT\\'s capabilities (e.g., "help", "what can you do?"), use Structure 1. Set `intent` to `SHOW_HELP`, `kit_core_command` to null, and `response_text` to null (KIT.py will display the help message locally).
- If the query is a specific question about *how to use* a KIT command or *how to achieve a task* using KIT (e.g., "How do I use find with dates?", "What parameters does the update command take?", "How can I find notes by tag?", "What is the way to add content to a note?", "Show me an example of adding a note with properties"), and you cannot confidently answer it from the information already in this prompt, use Structure 1. Set `intent` to `ANSWER_FROM_HELP_CONTENT_REQUEST`, `kit_core_command` to null, and set `response_text` to the user's original question that you need help answering. KIT.py will then provide you with the full help documentation in a subsequent call to answer that specific question. Distinguish these "how-to" questions from direct commands to execute an action.
- If you need to ask the user for clarification because their request is ambiguous or missing information for a command (and it's NOT a general "how-to" question about command usage as described above, nor a general help request), use Structure 1. Set `intent` to `REQUEST_CLARIFICATION`, `kit_core_command` to null, and `response_text` to your clarifying question.

**Sequential Actions (`actions_list` - Structure 2):**
- Use Structure 2 if and only if the user\\'s single query explicitly asks for multiple distinct KITCore operations to be performed in sequence (e.g., "Create a note about X with tag Y, then find all notes tagged Z", or "Add note \'A\' then add note \'B\'").
- Each item in the `actions_list` must be a complete action object with `intent`, `kit_core_command`, and `parameters`.
- Do NOT use Structure 2 for simple queries or conversational responses.
- If a query involves multiple actions AND a conversational part, prioritize Structure 2 for the actions, and Gemini can handle the conversational aspect in how it processes the overall interaction (the overall `output_tone` can guide KIT.py).

**Contextual Follow-up Command Handling (Applies to single actions or actions within `actions_list`):**

**1. CRITICALLY IMPORTANT for `find_notes` Ambiguous Follow-ups:**
    - Check the IMMEDIATELY PRECEDING assistant message in the CONVERSATION HISTORY.
    - If that message was the result of a `find_notes` command and LISTED MULTIPLE notes (e.g., "Found 3 note(s): ..."), AND the user\\'s current query is a follow-up action (like \'delete it\', \'update it\', \'add a tag to it\', \'tell me more about the second one\') that refers to those notes ambiguously (e.g., using "it", "that one", "the first one", "the last one", or by ordinal position when multiple are present):
        - You MUST NOT try to guess or pick one, even if it seems like a plausible default (like the first or last).
        - You MUST use Structure 1, set `intent` to `REQUEST_CLARIFICATION`, `kit_core_command` to null, and your `response_text` MUST ask the user to specify the `original_id` of the note they mean. For example: "I found a few notes. Which one are you referring to? Please provide its Original ID." or "To make sure I update the correct note, could you please give me its Original ID?".
    - If the preceding assistant message from `find_notes` listed only a SINGLE note, you can then assume pronouns like "it" or "that note" refer to that single note for follow-up actions, and proceed with generating the KITCore command with the correct `original_id` (using Structure 1 or as part of an `actions_list` in Structure 2 if appropriate).

**2. Specific Handling for "another one" / "do that again" after `add_note`:**
    - Check the IMMEDIATELY PRECEDING user command AND assistant response in the CONVERSATION HISTORY.
    - If the user\\'s previous command resulted in a successful `add_note` (e.g., Assistant: "Note created successfully. Original ID: X"), AND the user\\'s current query is a very short, generic follow-up like "another one", "do that again", "add another", "one more":
        - Infer the intent is `add_note` again.
        - Look at the parameters used for the *previous* `add_note` command (from the history).
        - Reuse any `--tags` or `--props` from that previous command if they were present.
        - The `--content` for this new note is LIKELY different.
        - Therefore, you MUST use Structure 1, set `intent` to `REQUEST_CLARIFICATION`, `kit_core_command` to `add` (or null if asking before forming the command), and your `response_text` MUST ask for the content of the new note. For example, if the previous note had tag \'beta\': "Okay, creating another note with tag \'beta\'. What content should this new note have?" or "Sure, another one with tags \'beta\'. What\\'s the content?". Do NOT generate an `add` command with empty or guessed content in this scenario; ALWAYS ask for the new content.

- If the user\\'s request is vague or missing information needed for a command (NOT covered by the specific follow-up rules above), use Structure 1 to ask clarifying questions. For example, if they say "update note" without an ID, set `intent` to `REQUEST_CLARIFICATION` and `response_text` to "Which note (original_id) would you like to update?".

**General Instructions (Applies to single actions or actions within `actions_list`):**
- Ensure all parameter values for KITCore commands are strings, except for `original_id` and `older-than-days` which must be integers. The `tag` parameter for `add-tag` and `remove-tag` is a string.
- Convert user tag lists (e.g. [\\\\\"tag1\\\\\", \\\\\"tag2\\\\\"]) into a comma-separated string (e.g. \\\\\"tag1,tag2\\\\\") for the `add` and `update --new_tags` commands.
- The `find` command is for general searching. For specific tag additions/removals, use `add-tag` or `remove-tag`.
- If the user asks to delete a note, assume `soft-delete` unless they explicitly ask to `purge`.
User Query to process now:
"""
    return prompt

def execute_kit_core_command(command_args: list[str]) -> tuple[str, str, int]:
    kit_core_path = os.path.join(PROJECT_ROOT, "KITCore.py")
    env = os.environ.copy()
    env["PYTHONPATH"] = PROJECT_ROOT + os.pathsep + env.get("PYTHONPATH", "")
    try:
        process = subprocess.run(
            [sys.executable, kit_core_path] + command_args,
            capture_output=True, text=True, check=False, cwd=PROJECT_ROOT, env=env
        )
        return process.stdout, process.stderr, process.returncode
    except FileNotFoundError:
        if agent_logger: agent_logger.error(f"KITCore.py not found at {kit_core_path}")
        return "", f"Error: KITCore.py not found at {kit_core_path}", 1
    except Exception as e:
        if agent_logger: agent_logger.error(f"An unexpected error occurred in execute_kit_core_command: {e}")
        return "", f"An unexpected error occurred: {e}", 1

def format_kit_response(kit_core_stdout: str, kit_core_stderr: str, returncode: int, tone: str | None) -> str:
    output_message = ""
    processed_tone = tone.lower() if tone else "concise"
    if returncode == KITCORE_EXEC_ERROR_RETURN_CODE:
        output_message = f"I encountered a critical problem trying to run my core functions: {kit_core_stderr.strip()}. Please check the logs."
    elif kit_core_stderr:
        error_prefix = ""
        if processed_tone == "formal": error_prefix = "An error was encountered: "
        elif processed_tone == "concise": error_prefix = "Error: "
        output_message = f"{error_prefix}{kit_core_stderr.strip()}"
    elif kit_core_stdout:
        success_prefix = ""
        if processed_tone == "formal": success_prefix = "The requested operation was successful:\\n"
        output_message = f"{success_prefix}{kit_core_stdout.strip()}"
    elif returncode == 0:
        if processed_tone in ["friendly", "helpful"]: output_message = "Okay, consider it done! Looks like everything went smoothly."
        elif processed_tone == "formal": output_message = "The command executed successfully with no direct output."
        else: output_message = "Command executed successfully."
    else:
        output_message = f"The operation finished with exit code {returncode}. Details might be in KITCore's output or logs."
    return output_message

def get_current_user_name() -> str | None:
    if agent_logger: agent_logger.info("Checking for user name...")
    else: print("Checking for user name...")
    # Use the direct tool_get_setting for internal use in KIT.py for user_name
    name = tool_get_setting("user_name") 
    if name:
        if agent_logger: agent_logger.info(f"Found user name: {name}")
        else: print(f"Found user name: {name}")
        return name
    if agent_logger: agent_logger.info("User name not found in settings.")
    else: print("User name not found in settings.")
    return None

def main():
    global agent_logger, trace_logger
    run_timestamp_str = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    print("KIT Agent starting...")
    print(f"Run timestamp: {run_timestamp_str}")
    print("Initializing logging system and settings...")

    trace_enabled_this_session = False
    prompt_for_trace_setting = True
    print("Checking for existing trace logging setting...")
    trace_setting_stdout, trace_setting_stderr, trace_setting_rc = execute_kit_core_command(
        ["get_setting", "--key", "trace_logging_enabled"]
    )
    if trace_setting_rc == 0 and trace_setting_stdout and trace_setting_stdout.startswith("trace_logging_enabled: "):
        current_trace_setting = trace_setting_stdout.split(": ", 1)[1].strip().lower()
        if current_trace_setting == "true":
            trace_enabled_this_session = True
            prompt_for_trace_setting = False
            print(f"Trace logging is ENABLED based on saved preference.")
        elif current_trace_setting == "false":
            trace_enabled_this_session = False
            prompt_for_trace_setting = False
            print(f"Trace logging is DISABLED based on saved preference.")
        else:
            print(f"Found invalid trace logging setting: '{current_trace_setting}'. Will ask for preference.")
    elif trace_setting_rc == KITCORE_EXEC_ERROR_RETURN_CODE:
        print(f"Critical failure trying to get trace_logging_enabled setting. Defaulting to DISABLED and will not prompt for safety.", file=sys.stderr)
        trace_enabled_this_session = False
        prompt_for_trace_setting = False
    else:
        if trace_setting_stderr:
             print(f"Note: Could not retrieve trace_logging_enabled setting from KITCore: {trace_setting_stderr.strip()}")
        print("Trace logging setting not found. Will ask for preference.")

    if prompt_for_trace_setting:
        try:
            default_text_for_prompt = "yes" if trace_enabled_this_session else "no"
            prompt_message = f"Enable detailed trace logging for this session? (yes/no) [Default if empty: {default_text_for_prompt}]: "
            trace_input = input(prompt_message).strip().lower()
            if trace_input == 'yes': trace_enabled_this_session = True
            elif trace_input == 'no': trace_enabled_this_session = False
            print(f"Trace logging for this session will be: {'ENABLED' if trace_enabled_this_session else 'DISABLED'}.")
            set_tr_val = "true" if trace_enabled_this_session else "false"
            print("Saving trace logging preference...")
            _, set_trace_stderr, set_trace_rc = execute_kit_core_command(
                ["set_setting", "--key", "trace_logging_enabled", "--value", set_tr_val]
            )
            if set_trace_rc != 0:
                if set_trace_rc != KITCORE_EXEC_ERROR_RETURN_CODE:
                     print(f"Warning: Could not save trace_logging_enabled setting ('{set_tr_val}') to KITCore: {set_trace_stderr.strip()}", file=sys.stderr)
            else:
                print(f"Trace logging preference ('{set_tr_val}') saved to KITCore.")
        except KeyboardInterrupt:
            print("\\nSetup for trace logging interrupted. Exiting KIT Agent.")
            sys.exit(0)
        except EOFError: 
            print("\\nEOF reached during setup. Using default trace setting. Exiting KIT Agent.")
            sys.exit(1)
    
    agent_logger, trace_logger = setup_kit_loggers(run_timestamp_str, trace_enabled_this_session)
    agent_logger.info("Logging system initialized.")

    # Perform automatic daily purge check at startup
    run_automatic_daily_purge()

    user_name = get_current_user_name()
    if user_name is None:
        try:
            agent_logger.info("User name not found in settings. Prompting user.")
            new_name_input = input("It looks like I don't have your name. What should I call you? (Leave blank to skip): ").strip()
            if new_name_input:
                agent_logger.info(f"Attempting to save user name: '{new_name_input}'")
                _, stderr_name_save, rc_name_save = execute_kit_core_command(["set_setting", "--key", "user_name", "--value", new_name_input])
                if rc_name_save == 0:
                    user_name = new_name_input
                    agent_logger.info(f"User name '{user_name}' saved successfully.")
                else:
                    if rc_name_save == KITCORE_EXEC_ERROR_RETURN_CODE:
                        agent_logger.error(f"Critical error attempting to save user name '{new_name_input}'. See previous logs. Name not saved.")
                    else:
                        agent_logger.error(f"Could not save user name '{new_name_input}'. KITCore error: {stderr_name_save.strip()}")
            else:
                agent_logger.info("User chose not to provide a name for this session.")
        except KeyboardInterrupt:
            agent_logger.info("User name setup interrupted by user. Exiting KIT Agent.")
            sys.exit(0)
        except EOFError:
            agent_logger.warning("EOF reached while prompting for user name. Continuing without name.")

    welcome_msg_main = "Type 'exit' or 'quit' to stop."
    if user_name:
        welcome_msg_main = f"Welcome back, {user_name}! " + welcome_msg_main
    else: # If user_name is still None or an empty string after attempting to get/set it
        welcome_msg_main = "Welcome to KIT! " + welcome_msg_main # Generic welcome
    agent_logger.info(f"KIT Agent activated. {welcome_msg_main}")


    conversation_history = deque(maxlen=MAX_HISTORY_TURNS * 2) 
    # Fetch AI model preference once at the start
    ai_model_to_use = tool_get_setting("ai_model_preference")
    if not ai_model_to_use or not isinstance(ai_model_to_use, str):
        # Fallback to the default defined in settings_tool.py if not found or invalid type
        from KITCore.tools.settings_tool import DEFAULT_SETTINGS as CORE_DEFAULT_SETTINGS
        ai_model_to_use = CORE_DEFAULT_SETTINGS.get("ai_model_preference", "gemini-1.0-pro") # Final fallback
        agent_logger.info(f"AI model preference not set or invalid, falling back to: {ai_model_to_use}")
    else:
        agent_logger.info(f"Using AI model preference: {ai_model_to_use}")

    while True:
        try:
            query = input("> ").strip()
            if query.lower() in ["exit", "quit"]:
                agent_logger.info("Exiting KIT Agent.")
                break
            
            if not query:
                continue

            conversation_history.append({"role": "user", "content": query})
            agent_logger.info(f"User query: {query}")
            
            current_date_iso = datetime.now().isoformat()
            current_gemini_prompt_base = get_gemini_master_prompt(user_name, conversation_history)
            processed_gemini_prompt = current_gemini_prompt_base.replace("{{{{current_date_iso_for_gemini_do_not_modify}}}}", current_date_iso)
            
            final_prompt_for_gemini = processed_gemini_prompt + query
            if trace_logger:
                trace_logger.debug(f"Full prompt to Gemini:\n{final_prompt_for_gemini}")

            gemini_response_text, gemini_error_message = get_gemini_response(final_prompt_for_gemini, model_name=ai_model_to_use)
            if trace_logger:
                trace_logger.debug(f"Gemini raw response text: {gemini_response_text}")
                if gemini_error_message:
                    trace_logger.debug(f"Gemini error message: {gemini_error_message}")

            if gemini_error_message:
                agent_logger.error(f"Error from Gemini client: {gemini_error_message}")
                print(f"Sorry, I encountered an issue: {gemini_error_message}")
                conversation_history.append({"role": "assistant", "content": f"Sorry, I encountered an issue: {gemini_error_message}"})
                continue

            if not gemini_response_text:
                agent_logger.error("Received no response text from Gemini.")
                print("Sorry, I didn't get a response. Please try again.")
                conversation_history.append({"role": "assistant", "content": "Sorry, I didn't get a response. Please try again."})
                continue

            final_assistant_response_for_history = ""
            
            try:
                cleaned_response_text = gemini_response_text.strip()
                if cleaned_response_text.startswith("```json"):
                    cleaned_response_text = cleaned_response_text[7:]
                if cleaned_response_text.endswith("```"):
                    cleaned_response_text = cleaned_response_text[:-3]
                
                gemini_response_json = json.loads(cleaned_response_text)
                if trace_logger:
                    trace_logger.debug(f"Parsed Gemini JSON: {json.dumps(gemini_response_json)}")

                output_tone = gemini_response_json.get("output_tone", "concise")
                intent = gemini_response_json.get("intent")

                if intent == "SHOW_HELP":
                    agent_logger.info("Gemini returned SHOW_HELP intent.")
                    help_message = get_kit_static_help_message()
                    print(help_message)
                    final_assistant_response_for_history = help_message
                elif intent == "ANSWER_FROM_HELP_CONTENT_REQUEST":
                    agent_logger.info("Gemini returned ANSWER_FROM_HELP_CONTENT_REQUEST intent.")
                    original_user_question = gemini_response_json.get("response_text")
                    if not original_user_question:
                        agent_logger.error("ANSWER_FROM_HELP_CONTENT_REQUEST intent received, but no original_user_question (response_text) was found in Gemini's JSON.")
                        fallback_message = "I was going to look up the answer to your question in the help content, but I seem to have lost the original question. Please try again."
                        print(fallback_message)
                        final_assistant_response_for_history = fallback_message
                    else:
                        agent_logger.info(f"Original question for help Q&A: {original_user_question}")
                        full_help_text = get_kit_static_help_message()

                        # Construct history block for Q&A prompt
                        qna_history_block = ""
                        if conversation_history:
                            history_items = []
                            # conversation_history already includes the current user query that triggered this Q&A
                            for turn in conversation_history:
                                role = "User" if turn["role"] == "user" else "Assistant"
                                # Escape for f-string using ''' delimiters, ensuring backslashes are literal and ''' is escaped.
                                escaped_content = str(turn['content']).replace('\\', '\\\\').replace("'''", "\'\'\'")
                                history_items.append(f"{role}: {escaped_content}")
                            if history_items:
                                qna_history_block = "CONVERSATION HISTORY:\n" + "\n".join(history_items) + "\n\n"
                        
                        secondary_qna_prompt = f'''{qna_history_block}You are an assistant tasked with answering the user\'s latest question from the CONVERSATION HISTORY.
Base your answer *only* on the provided KIT system help documentation and the CONVERSATION HISTORY.
Your primary goal is to help the user understand how to interact with the KIT agent using natural language or by providing command examples if appropriate.

--- KIT HELP DOCUMENTATION START ---
{full_help_text}
--- KIT HELP DOCUMENTATION END ---

The user's question to answer is the last user message in the CONVERSATION HISTORY above.
Analyze the USER'S QUESTION (from history) and the KIT HELP DOCUMENTATION carefully.

Your response should EITHER be a natural language explanation OR a direct command example, based on the following STRICT criteria:

1.  **CRITERIA FOR PROVIDING A DIRECT COMMAND EXAMPLE:**
    *   Only provide a direct command example if the USER'S QUESTION (from history) uses phrases like: "show me the command for...", "what is the exact command to...", "give me the syntax for...", "command example for...", or explicitly asks for a "terminal command", "CLI syntax", or similar. Consider the context from the history.
    *   If these specific phrases are present, AND the context from history makes it clear WHICH command they are referring to, provide the relevant command example(s) from the documentation. Frame it as giving an example of the command. If the command is ambiguous even with history, ask for clarification.

2.  **CRITERIA FOR PROVIDING NATURAL LANGUAGE GUIDANCE (Default Behavior):**
    *   For ALL OTHER questions about how to perform a task (e.g., "How do I filter notes?", "What's the way to add a tag?", "How can I find notes by tag?"), you MUST explain how the user can ask the KIT agent (you) to perform the action in natural language.
    *   DO NOT just output the raw CLI command in these cases unless criteria 1 is met.
    *   Instead, use the information in the documentation to formulate a sentence describing the natural language query. For example, if the documentation for finding notes by tag is `find --tags "<tag1>,<tag2>"`, and the user asks "How can I find notes by tag?", you should respond with something like: "You can ask me to find notes by specific tags. For instance, say: 'Find notes tagged project_alpha and urgent'."

- Frame your answer as if you are the KIT agent itself.
- Base your answer *only* on the provided KIT HELP DOCUMENTATION and CONVERSATION HISTORY.
- If the answer cannot be found in the documentation, or if the command is still ambiguous, state that clearly.
'''
                        if trace_logger:
                            trace_logger.debug(f"Secondary Q&A prompt to Gemini:\n{secondary_qna_prompt}")
                        
                        qna_answer_text, qna_error_message = get_gemini_response(secondary_qna_prompt, model_name=ai_model_to_use)
                        
                        if trace_logger:
                            trace_logger.debug(f"Gemini Q&A raw response text: {qna_answer_text}")
                            if qna_error_message:
                                trace_logger.debug(f"Gemini Q&A error message: {qna_error_message}")

                        if qna_error_message:
                            agent_logger.error(f"Error from Gemini client during Q&A call: {qna_error_message}")
                            error_message_to_user = f"Sorry, I encountered an issue while trying to answer your question using the help content: {qna_error_message}"
                            print(error_message_to_user)
                            final_assistant_response_for_history = error_message_to_user
                        elif not qna_answer_text:
                            agent_logger.error("Received no response text from Gemini for Q&A call.")
                            no_answer_message = "Sorry, I tried to look that up in the help content but didn't get an answer back. Please try rephrasing or ask a different question."
                            print(no_answer_message)
                            final_assistant_response_for_history = no_answer_message
                        else:
                            # Attempt to clean up if Gemini wraps its Q&A response in markdown
                            cleaned_qna_answer = qna_answer_text.strip()
                            if cleaned_qna_answer.startswith("```") and cleaned_qna_answer.endswith("```"):
                                lines = cleaned_qna_answer.split('\n')
                                if len(lines) > 1:
                                    # Remove potential json/text specifier like ```json or ```text
                                    cleaned_qna_answer = '\n'.join(lines[1:-1]) if lines[0].startswith("```") else '\n'.join(lines)
                                else: # Only ``` ``` on one line with content in between
                                     cleaned_qna_answer = cleaned_qna_answer[3:-3].strip()
                            elif cleaned_qna_answer.startswith("```"):
                                lines = cleaned_qna_answer.split('\n')
                                if len(lines) > 1: 
                                    cleaned_qna_answer = '\n'.join(lines[1:]) if lines[0].startswith("```") else '\n'.join(lines)
                                else:
                                    cleaned_qna_answer = cleaned_qna_answer[3:].strip()

                            agent_logger.info(f"Gemini Q&A answer: {cleaned_qna_answer}")
                            print(cleaned_qna_answer)
                            final_assistant_response_for_history = cleaned_qna_answer

                elif "actions_list" in gemini_response_json and gemini_response_json["actions_list"]:
                    agent_logger.info(f"Gemini returned multiple actions: {len(gemini_response_json['actions_list'])} actions.")
                    all_actions_successful = True
                    aggregated_responses = []
                    for i, action_item in enumerate(gemini_response_json["actions_list"]):
                        action_intent = action_item.get("intent")
                        kit_core_cmd_name = action_item.get("kit_core_command")
                        parameters = action_item.get("parameters", {})
                        agent_logger.info(f"Executing action {i+1}/{len(gemini_response_json['actions_list'])}: intent='{action_intent}', command='{kit_core_cmd_name}', params={parameters}")
                        if kit_core_cmd_name:
                            command_to_run_args = [kit_core_cmd_name]
                            for param, value in parameters.items():
                                command_to_run_args.extend([f"--{param}", str(value)])
                            if trace_logger: trace_logger.debug(f"Executing KITCore command (action {i+1}): {command_to_run_args}")
                            response_stdout, response_stderr, returncode = execute_kit_core_command(command_to_run_args)
                            if trace_logger:
                                trace_logger.debug(f"KITCore stdout (action {i+1}): {response_stdout.strip()}")
                                trace_logger.debug(f"KITCore stderr (action {i+1}): {response_stderr.strip()}")
                                trace_logger.debug(f"KITCore returncode (action {i+1}): {returncode}")
                            formatted_response = format_kit_response(response_stdout, response_stderr, returncode, output_tone)
                            print(formatted_response)
                            aggregated_responses.append(formatted_response)
                            if returncode != 0:
                                agent_logger.error(f"Action {i+1} ('{kit_core_cmd_name}') failed. Stopping sequence.")
                                all_actions_successful = False
                                break
                        else:
                            agent_logger.warning(f"Action {i+1} in actions_list has no kit_core_command. Intent: {action_intent}")
                            response_text = action_item.get("response_text", "I found an action I couldn't process.")
                            print(response_text)
                            aggregated_responses.append(response_text)
                    final_assistant_response_for_history = "\\n".join(aggregated_responses)
                    if not all_actions_successful: agent_logger.info("One or more actions in the sequence failed.")
                    else: agent_logger.info("All actions in sequence executed successfully.")
                elif gemini_response_json.get("kit_core_command"):
                    kit_core_cmd_name = gemini_response_json["kit_core_command"]
                    parameters = gemini_response_json.get("parameters", {})
                    agent_logger.info(f"Gemini returned single action: intent='{intent}', command='{kit_core_cmd_name}', params={parameters}")
                    command_to_run_args = [kit_core_cmd_name]
                    for param, value in parameters.items():
                        command_to_run_args.extend([f"--{param}", str(value)])
                    if trace_logger: trace_logger.debug(f"Executing KITCore command: {command_to_run_args}")
                    response_stdout, response_stderr, returncode = execute_kit_core_command(command_to_run_args)
                    if trace_logger:
                        trace_logger.debug(f"KITCore stdout: {response_stdout.strip()}")
                        trace_logger.debug(f"KITCore stderr: {response_stderr.strip()}")
                        trace_logger.debug(f"KITCore returncode: {returncode}")
                    formatted_response = format_kit_response(response_stdout, response_stderr, returncode, output_tone)
                    print(formatted_response)
                    final_assistant_response_for_history = formatted_response
                    if returncode == 0: agent_logger.info(f"KITCore command '{kit_core_cmd_name}' executed successfully.")
                    else: agent_logger.warning(f"KITCore command '{kit_core_cmd_name}' finished with return code {returncode}.")
                elif gemini_response_json.get("response_text"):
                    response_text = gemini_response_json["response_text"]
                    agent_logger.info(f"Gemini returned conversational response: intent='{intent}'")
                    if trace_logger: trace_logger.debug(f"Response text from Gemini: {response_text}")
                    print(response_text)
                    final_assistant_response_for_history = response_text
                else:
                    agent_logger.warning("Gemini response JSON did not match expected structures (no SHOW_HELP, actions_list, kit_core_command, or response_text).")
                    fallback_message = "I'm not sure how to proceed with that response. Please try rephrasing."
                    print(fallback_message)
                    final_assistant_response_for_history = fallback_message
            except json.JSONDecodeError as e:
                agent_logger.error(f"Failed to parse Gemini's response as JSON: {e}")
                agent_logger.error(f"Raw Gemini response was: {gemini_response_text}")
                fallback_message = "Sorry, I had trouble understanding the response format. Could you try again?"
                print(fallback_message)
                final_assistant_response_for_history = fallback_message
            except Exception as e:
                agent_logger.error(f"An unexpected error occurred processing Gemini response or KITCore command: {e}", exc_info=True)
                fallback_message = "An unexpected error occurred. Please check the logs."
                print(fallback_message)
                final_assistant_response_for_history = fallback_message
            
            if final_assistant_response_for_history:
                conversation_history.append({"role": "assistant", "content": final_assistant_response_for_history})
                if trace_logger:
                    trace_logger.debug(f"Assistant response added to history: {final_assistant_response_for_history}")

        except KeyboardInterrupt:
            agent_logger.info("User initiated exit (Ctrl+C).")
            print("\\nExiting KIT Agent...")
            break
        except Exception as e:
            agent_logger.critical(f"Critical unexpected error in main loop: {e}", exc_info=True)
            print(f"A critical error occurred: {e}. Exiting. Check logs for details.")
            break

if __name__ == "__main__":
    main()