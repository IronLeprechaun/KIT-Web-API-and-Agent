# KIT_Web Technical Documentation

This document provides a more in-depth technical overview of the KIT_Web application, covering its architecture, key components, and workflows.

## Table of Contents

1.  [Architecture Overview](#architecture-overview)
2.  [Backend Details](#backend-details)
    *   [Directory Structure](#backend-directory-structure)
    *   [Core Modules (`KITCore`, `KIT`)](#core-modules)
    *   [API Layer (`api/`)](#api-layer)
    *   [Configuration (`config.py`, `config_settings.py`)](#backend-configuration)
    *   [Logging System](#logging-system)
    *   [Database and Migrations](#database-and-migrations)
3.  [Frontend Details](#frontend-details)
    *   [Directory Structure](#frontend-directory-structure)
    *   [Key Components (`App.tsx`, `NoteList.tsx`, `ChatInterface.tsx`)](#frontend-key-components)
    *   [State Management (Redux Toolkit)](#state-management)
    *   [Styling (MUI)](#styling)
4.  [AI Interaction Workflow](#ai-interaction-workflow)
    *   [System Prompt](#system-prompt)
    *   [WebSocket Communication](#websocket-communication)
    *   [Intent Processing](#intent-processing)
    *   [Conversation History](#conversation-history)
5.  [Testing](#testing)
6.  [Future Enhancements](#future-enhancements)

---

## 1. Architecture Overview

KIT_Web employs a client-server architecture:

*   **Backend:** A Python application built with FastAPI. It serves a RESTful API for standard CRUD operations and a WebSocket endpoint for real-time AI chat interactions. It integrates the original `KITCore` (for note/settings management) and `KIT` (for AI logic) modules.
*   **Frontend:** A single-page application (SPA) built with React, TypeScript, and Vite. It uses Material-UI (MUI) for components and Redux Toolkit for state management. It communicates with the backend via HTTP requests (Axios) and WebSockets.

```mermaid
graph LR
    subgraph Frontend (React + Vite)
        direction LR
         SPA[Single Page Application]
        subgraph Components
            direction TB
            Chat[ChatInterface.tsx]
            Notes[NoteList.tsx]
            AppLayout[App.tsx]
        end
        subgraph State (Redux)
            direction TB
            ChatSlice[chatSlice.ts]
            NotesSlice[notesSlice.ts]
        end
        Axios[Axios Client] -- HTTP --> API
        WSClient[WebSocket Client] -- WS --> AIWS
    end

    subgraph Backend (FastAPI)
        direction LR
        API[REST API Router]
        AIWS[AI WebSocket Router]

        subgraph Services
            direction TB
            AIService[ai_service.py]
            NoteService[note_service.py]
            OtherServices[...]
        end

        subgraph CoreLogic
            direction TB
            KITGemini[KIT/gemini_client.py]
            KITCoreTools[KITCore/tools/]
            DBManager[KITCore/database_manager.py]
        end

        AIService -- Uses --> KITGemini
        NoteService -- Uses --> KITCoreTools
        OtherServices -- Uses --> KITCoreTools
        KITCoreTools -- Interacts --> DBManager
        DBManager -- SQLite --> Database[(kit_agent.db)]

        API -- Calls --> NoteService
        API -- Calls --> OtherServices
        AIWS -- Calls --> AIService
    end

    SPA -- Interacts --> Chat
    SPA -- Interacts --> Notes
    Chat -- Dispatches/Selects --> ChatSlice
    Notes -- Dispatches/Selects --> NotesSlice
```

## 2. Backend Details

Located in `KIT_Web/backend/`.

### Backend Directory Structure

*   **`KITCore/`**: Contains the original core logic for note operations (`note_tool.py`), settings (`settings_tool.py`), and database interactions (`database_manager.py`). This code has been adapted to run within the web backend context.
*   **`KIT/`**: Houses the AI-specific logic, including the `GeminiClient` (`gemini_client.py`) for interacting with the Google Gemini API and the primary AI orchestration logic (`KIT.py` - though much of its direct use is now superseded by `ai_service.py`). `logger_utils.py` from here is used by `ai_service.py`.
*   **`api/`**: The FastAPI application.
    *   `app.py`: Main application setup, middleware (CORS), and router includes.
    *   `routes/`: API route definitions (e.g., `notes.py`, `ai.py`).
    *   `services/`: Business logic layer (e.g., `note_service.py`, `ai_service.py`).
    *   `alembic/`: Alembic migration scripts and configuration (`alembic.ini`).
    *   `config_settings.py`: Specific settings, currently for log rotation counts.
    *   `auth_utils.py`: Placeholder for authentication utilities.
    *   `requirements.txt`: Python dependencies for the backend API.
*   **`logs/`**: Stores timestamped, rotating log files for the backend and AI services.
*   **`tests/`**: Contains unit tests for backend components (e.g., `test_note_tool.py`).
*   **`config.py`**: Main backend configuration file (database path, default log levels).
*   **`.venv/`**: Python virtual environment.

### Core Modules (`KITCore`, `KIT`)

These modules were originally part of a standalone Python application and have been integrated into the `KIT_Web/backend/` directory. 

*   **`KITCore.database_manager`**: Manages the SQLite database connection and schema. It defines the `kit_notes` and `kit_tags` tables.
*   **`KITCore.tools.note_tool`**: Provides functions for creating, retrieving, updating, and deleting notes and their associated tags. Directly interacts with the database via `database_manager`.
*   **`KITCore.tools.settings_tool`**: Manages application settings stored in a `settings` table in the database.
*   **`KIT.gemini_client`**: A dedicated client for interacting with the Google Gemini API. Handles API key management, request formatting, and response parsing.
*   **`KIT.logger_utils`**: Sets up `kit_agent` and `kit_trace` loggers, now with timestamped filenames and log rotation capabilities, used by `ai_service.py`.

### API Layer (`api/`)

*   **`app.py`**: Initializes the FastAPI app, sets up CORS, includes API routers, and calls `setup_logging()`.
*   **Routers (`api/routes/`)**: Define API endpoints. For example:
    *   `notes.py`: `/api/notes/` for note CRUD operations.
    *   `ai.py`: `/api/ai/chat` WebSocket endpoint for AI interactions.
*   **Services (`api/services/`)**: Contain the business logic decoupled from the routing layer.
    *   `note_service.py`: Handles logic for note operations, calling `KITCore.tools.note_tool`.
    *   `ai_service.py`: Manages AI chat sessions, processes user queries, interacts with `GeminiClient`, and formats responses. This is the main orchestrator for AI functionality.

### Backend Configuration

*   **`KIT_Web/backend/config.py`**: Defines `DEFAULT_LOG_LEVEL`, `KIT_DATABASE_DIR`, `KIT_DATABASE_NAME`, and `KIT_BACKUP_DIR`. This is the primary config file for paths and core logging behavior.
*   **`KIT_Web/backend/api/config_settings.py`**: Currently defines `MAX_BACKEND_LOG_FILES` and `MAX_AISERVICE_LOG_FILES` for the log rotation feature.
*   **Environment Variables**: `GEMINI_API_KEY` is crucial and must be set in the environment where the backend server runs.

### Logging System

A robust logging system is in place:

*   **FastAPI Application Logs (`backend_api_*.log`):**
    *   Setup in `api/app.py` via `setup_logging()`.
    *   Uses Python's `logging.config.dictConfig`.
    *   Log files are timestamped (e.g., `backend_api_20240523_120000.log`).
    *   Rotation: Keeps the `MAX_BACKEND_LOG_FILES` most recent logs.
*   **AI Service Logs (`kit_agent_*.log`, `kit_trace_*.log`):**
    *   Setup by `AIService` using `KIT.logger_utils.setup_kit_loggers()`.
    *   Timestamps are based on `AIService` initialization.
    *   Rotation: Keeps the `MAX_AISERVICE_LOG_FILES` most recent `kit_agent_*.log` files.
*   **Log Directory:** All logs are stored in `KIT_Web/backend/logs/`.

### Database and Migrations

*   **Database:** SQLite, file located at `KIT_Web/backend/KITCore/database/kit_agent.db`.
*   **Schema:** Managed by `KITCore.database_manager.py` (table creation) and extended/tracked by Alembic.
*   **Alembic Migrations:** Located in `KIT_Web/backend/api/alembic/`. Configuration in `KIT_Web/backend/api/alembic.ini`. Used to manage schema changes after initial setup.
    *   The `env.py` for Alembic targets the metadata from `KITCore.database_manager`. Ensure `sys.path` is correctly configured if running Alembic commands from a different context.

## 3. Frontend Details

Located in `KIT_Web/frontend/`.

### Frontend Directory Structure

*   **`src/`**: Main source code.
    *   `main.tsx`: Entry point, renders `App` and sets up Redux store, MUI theme.
    *   `App.tsx`: Main application layout (two-column structure for chat and notes).
    *   `App.css`, `index.css`: Global styles.
    *   `theme.ts`: MUI theme configuration.
    *   `components/`:
        *   `ChatInterface.tsx`: Manages the chat UI, WebSocket connection, message display, user input, and AI context history display trigger.
        *   `NoteList.tsx`: Displays the list of notes and the AI context history.
    *   `stores/`:
        *   `store.ts`: Redux store configuration.
        *   `notesSlice.ts`: Redux slice for managing notes state (fetching, AI context history).
        *   `chatSlice.ts`: Redux slice for managing chat messages and WebSocket status.
*   **`public/`**: Static assets.
*   Configuration files: `package.json`, `vite.config.ts`, `tsconfig.json`, ESLint/Prettier configs.

### Frontend Key Components

*   **`App.tsx`**: Sets up the main two-column layout using MUI `Box` components with Flexbox. Manages the overall structure ensuring independent scrolling for the chat and notes sections.
*   **`ChatInterface.tsx`**: 
    *   Establishes and manages the WebSocket connection to `/api/ai/chat`.
    *   Handles sending user messages and conversation history to the backend.
    *   Receives and displays AI responses, including actions and feedback.
    *   Uses `chatSlice` to store messages and connection status.
    *   Uses `notesSlice` to trigger updates to AI context history.
    *   Renders messages with sender information and timestamps.
    *   Uses `react-markdown` to render AI help messages.
*   **`NoteList.tsx`**: 
    *   Subscribes to `notesSlice` to display the current list of notes.
    *   Displays note ID, content, creation date, and tags.
    *   Renders the `aiContextHistory` from `notesSlice`, showing user queries and AI actions (like note creation, updates).
    *   Includes a "Clear History" button for the AI context.

### State Management (Redux Toolkit)

*   **`store.ts`**: Configures the root Redux store.
*   **`notesSlice.ts`**: 
    *   Manages an array of notes (`Note[]`).
    *   Handles fetching all notes via an async thunk (`fetchNotes`) using Axios.
    *   Manages `aiContextHistory` (an array of `AIContextEntry`) which stores a log of user queries and the AI's understanding/actions related to notes.
    *   Reducers: `setNotes`, `addNote`, `updateNoteInList`, `removeNoteFromList`, `updateAIContextHistory`, `clearAIContextHistory`.
*   **`chatSlice.ts`**: 
    *   Manages an array of chat messages (`ChatMessage[]`).
    *   Manages WebSocket connection status (`websocketStatus`).
    *   Reducers: `addMessage`, `setWebsocketStatus`.

### Styling (MUI)

*   Material-UI (MUI) is used for UI components and styling.
*   A custom theme is defined in `theme.ts`.
*   `CssBaseline` provides consistent baseline styles.
*   MUI components like `Box`, `Paper`, `Typography`, `TextField`, `Button`, `List`, `ListItem` are used extensively.

## 4. AI Interaction Workflow

### System Prompt

The AI's behavior is heavily guided by a system prompt defined in `KIT_Web/backend/api/services/ai_service.py` (`KIT_SYSTEM_PROMPT`). This prompt instructs the AI to:
*   Act as a note management assistant.
*   Understand intents like `create_note`, `find_notes`, `update_note_content`, `add_tags_to_note`, `delete_note`, `find_note_by_id`, `show_help`.
*   Respond in a specific JSON format: `{"intent": "...", "entities": {...}, "response_text": "...", "action_feedback": "..."}`.
*   Handle note attributes like content, tags, and IDs.

### WebSocket Communication

1.  **Connection:** Frontend (`ChatInterface.tsx`) establishes a WebSocket connection to `ws://localhost:8000/api/ai/chat`.
2.  **User Message:** When the user sends a message:
    *   Frontend sends a JSON object: `{"text": "user query", "conversation_history": [...]}`.
    *   `conversation_history` includes previous user messages and AI `response_text` fields.
3.  **Backend Processing (`ai_service.py`):**
    *   Receives the message.
    *   Constructs a prompt for the Gemini API, including the system prompt, conversation history, and the current user query.
    *   Calls `GeminiClient.get_gemini_response()`.
4.  **AI Response Parsing:**
    *   The AI is expected to return JSON matching the system prompt's specified format.
    *   `ai_service.py` parses this JSON to extract `intent`, `entities`, `response_text`, and `action_feedback`.
5.  **Action Execution:** Based on the parsed `intent` and `entities`:
    *   `ai_service.py` calls appropriate methods in `NoteService` (e.g., `create_note`, `find_notes_by_criteria`, `update_note_content`).
    *   `NoteService` interacts with `KITCore.tools.note_tool`.
6.  **Feedback to Frontend:**
    *   The backend sends a JSON message back over WebSocket, structured like:
        ```json
        {
            "type": "ai_response" | "ai_action" | "error",
            "data": {
                "sender": "AI",
                "text": "AI response_text or error message",
                "original_user_query": "...", // The query that led to this
                "intent": "...",
                "action_feedback": "...",
                "action_data": { ... } // e.g., created_note, found_notes, updated_note_id
            }
        }
        ```
    *   `action_data` includes details like the created note, found notes, or IDs of affected notes.
7.  **Frontend Update:**
    *   `ChatInterface.tsx` receives the WebSocket message.
    *   Adds AI messages to `chatSlice`.
    *   If `action_data` is present and relevant (e.g., note created/updated/deleted), it dispatches actions to `notesSlice` (`fetchNotes` to refresh or `updateAIContextHistory`).

### Intent Processing

`ai_service.py` has specific handlers for each intent defined in the system prompt:
*   `create_note`: Extracts content and optional tags. Calls `NoteService.create_note()`.
*   `find_notes`: Extracts search terms (content, tags). Calls `NoteService.find_notes_by_criteria()`.
*   `update_note_content`: Extracts `note_id` and `new_content`. Calls `NoteService.update_note_content()`.
*   `add_tags_to_note`: Extracts `note_id` and `tags`. Calls `NoteService.add_tags_to_note()`.
*   `delete_note`: Extracts `note_id` (can be a list). Calls `NoteService.delete_notes_by_original_ids()`.
*   `find_note_by_id`: Extracts `note_id`. Calls `NoteService.find_note_by_original_id()`.
*   `show_help`: Sends back the predefined `KIT_AI_HELP_MESSAGE`.

### Conversation History

To enable contextual follow-up questions, the frontend (`ChatInterface.tsx`) sends a `conversation_history` array with each WebSocket message. This array contains objects `{ "role": "user" | "model", "parts": [{"text": "..."}] }` representing past turns. `ai_service.py` formats this history for the Gemini API.

## 5. Testing

*   **Backend:**
    *   Database tests are located in `KIT_Web/tests/database/` (e.g., `test_db_working.py`).
    *   API endpoint tests are located in `KIT_Web/tests/api/` (e.g., `test_endpoints.py`).
    *   Test orchestration scripts are located in `KIT_Web/scripts/` (`enhanced_tester.py`, `server_manager.py`).*   Running backend tests: `cd KIT_Web && python scripts/enhanced_tester.py --backend`
    *   Server health checks: `cd KIT_Web && python scripts/server_manager.py --health-check`

## 6. Future Enhancements

