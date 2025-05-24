# KIT Web Conversion Plan

## Overview
This document outlines the plan to convert the existing KIT Python application into a web-based application while maintaining the current codebase as a reference. The new web version will be developed in a separate `KIT_Web` directory. the old version is in the directory `OLD_VERSION_KIT_PY`

## Project Structure

```
KIT_Web/
├── backend/                 # Python backend (existing code + API layer)
│   ├── KITCore/            # Existing core functionality (copied and adapted)
│   │   ├── database_manager.py
│   │   ├── tools/
│   │   │   ├── note_tool.py
│   │   │   └── settings_tool.py
│   │   └── __init__.py
│   ├── KIT/                # Existing AI agent (copied and adapted)
│   │   ├── KIT.py
│   │   ├── gemini_client.py
│   │   └── logger_utils.py
│   │   └── __init__.py
│   ├── api/                # New REST API layer
│   │   ├── app.py          # FastAPI application
│   │   ├── alembic.ini
│   │   ├── requirements.txt
│   │   ├── config_settings.py # For log rotation counts etc.
│   │   ├── auth_utils.py
│   │   ├── __init__.py
│   │   ├── routes/
│   │   │   ├── notes.py
│   │   │   ├── tags.py
│   │   │   ├── settings.py
│   │   │   ├── ai.py
│   │   │   └── __init__.py
│   │   ├── services/
│   │   │   ├── ai_service.py
│   │   │   ├── note_service.py
│   │   │   ├── tag_service.py
│   │   │   ├── settings_service.py
│   │   │   └── __init__.py
│   │   └── alembic/        # Alembic migration scripts
│   │       └── ...
│   ├── logs/               # Directory for rotated log files
│   ├── tests/              # Backend tests
│   │   ├── test_note_tool.py
│   │   └── test_settings_tool.py
│   ├── config.py           # Main backend configuration (e.g. DB path, log level)
│   ├── README.md           # Backend specific README
│   └── .venv/              # Virtual environment
│
├── frontend/               # New React frontend
│   ├── src/
│   │   ├── components/     # UI components
│   │   │   ├── ChatInterface.tsx
│   │   │   └── NoteList.tsx
│   │   ├── stores/         # State management (Redux Toolkit)
│   │   │   ├── store.ts
│   │   │   ├── notesSlice.ts
│   │   │   └── chatSlice.ts
│   │   ├── App.tsx
│   │   ├── App.css
│   │   ├── index.css
│   │   ├── main.tsx
│   │   ├── theme.ts
│   │   └── vite-env.d.ts
│   ├── public/
│   ├── package.json
│   ├── package-lock.json
│   ├── tsconfig.json
│   ├── tsconfig.app.json
│   ├── tsconfig.node.json
│   ├── vite.config.ts
│   ├── .eslintrc.cjs
│   ├── .eslintignore
│   ├── .prettierrc.json
│   ├── index.html
│   └── README.md           # Frontend specific README
│
├── .git/
├── .gitignore
├── KIT_WEB_CONVERSION_PLAN.md # This file
├── OLD_VERSION_KIT_PY/      # The original Python-only project
│   └── ...
├── README.md                # Main project README
└── restart_dev_servers.ps1

```

## Development Phases

### Phase 1: Backend API Development (2 weeks)

1.  **API Layer Setup**
    *   [x] Set up FastAPI application (`KIT_Web/backend/api/app.py`)
    *   [x] Implement basic routing structure (notes, tags, settings, ai routers included in `app.py` with `/api` prefix)
    *   [ ] Add authentication middleware (Placeholder OAuth2PasswordBearer in `auth_utils.py`, needs full implementation)
    *   [x] Set up CORS (`CORSMiddleware` in `app.py`)
    *   [x] Basic security headers (Can be improved, but FastAPI provides some defaults)
    *   [x] Initial `requirements.txt` for backend dependencies.

2.  **Core API Endpoints**
    *   [x] Notes management endpoints (GET, POST, PUT (soft delete), DELETE (soft delete) via `NoteService`)
    *   [x] Tag management endpoints (GET, POST for adding tags to notes via `NoteService` & `TagService`)
    *   [x] Settings management endpoints (GET, POST for settings via `SettingsService`)
    *   [x] AI service endpoints (`/api/ai/chat` WebSocket functional via `ai_service.py`)

3.  **Database Integration**
    *   [x] Maintain existing SQLite database structure (via `KITCore/database_manager.py`)
    *   [x] Implement migration system (Alembic initialized in `KIT_Web/backend/api/alembic/` and configured for `kit_notes` and `kit_tags` tables)
    *   [x] Implement proper error handling (Enhanced in API routes and services)
    *   [x] Database connection pooling (Handled by SQLAlchemy in `KITCore`)

4.  **AI Service Integration & Logging**
    *   [x] Adapt `KITCore` and `KIT` modules for use within the FastAPI backend (`KIT_Web/backend/KITCore/` and `KIT_Web/backend/KIT/`)
    *   [x] `ai_service.py` orchestrates AI interaction using `GeminiClient`.
    *   [x] Implement WebSocket support for real-time AI responses (`/api/ai/chat`).
    *   [x] **Advanced Logging:**
        *   [x] Implemented rotating file logs for backend API (`backend_api_*.log` in `KIT_Web/backend/logs/`).
        *   [x] Implemented rotating file logs for AI service (`kit_agent_*.log`, `kit_trace_*.log` in `KIT_Web/backend/logs/`).
        *   [x] Configured maximum number of log files via `KIT_Web/backend/api/config_settings.py`.
        *   [x] Centralized logging setup in `app.py` and `logger_utils.py`.

### Phase 2: Frontend Basic Setup (2 weeks)

1.  **Project Setup**
    *   [x] Initialize React project with TypeScript (`KIT_Web/frontend` via Vite)
    *   [x] Set up build tools (Vite configured)
    *   [x] Configure ESLint and Prettier (`.eslintrc.cjs`, `.prettierrc.json`, scripts in `package.json`)
    *   [x] Set up testing framework (Vitest with React Testing Library)

2.  **Core Components**
    *   [x] Layout components (`App.tsx` with AppBar, main content area with independent scrolling columns)
    *   [ ] Navigation (Basic AppBar present, no interactive navigation yet)
    *   [x] Basic UI components (MUI `ThemeProvider`, `CssBaseline` in `main.tsx`)
    *   [x] Theme setup (`theme.ts` created with basic MUI theme)

3.  **State Management**
    *   [x] Set up Redux/Context API (Redux store configured in `stores/store.ts`)
    *   [x] Implement basic stores (`notesSlice.ts`, `chatSlice.ts` created)
    *   [ ] Add persistence layer (Not yet implemented)

4.  **API Integration**
    *   [x] Create API client services (`fetchNotes` in `notesSlice.ts` uses `axios`, WebSocket in `ChatInterface.tsx`)
    *   [x] Implement error handling (In `fetchNotes` thunk and reducer, WebSocket error handling)
    *   [x] Add loading states (In `notesSlice.ts` and `NoteList.tsx`, chat status in `chatSlice.ts`)

### Phase 3: Frontend Feature Implementation (3 weeks)

1.  **Note Management (Primarily via AI)**
    *   [x] Note creation/editing interface (AI intent `create_note` and `update_note_content` functional)
    *   [x] Note listing and search (AI intent `find_notes` and `find_note_by_id` functional; `NoteList.tsx` displays notes)
        *   [x] **Backend**: `/api/notes/` GET endpoint, AI intent processing in `ai_service.py`.
        *   [x] **Frontend**: `notesSlice.ts` for state, `NoteList.tsx` for display.
    *   [ ] Version history viewer (Placeholder)
    *   [x] Tag management interface (AI intent `add_tags_to_note` functional)

2.  **Search and Filtering**
    *   [x] Advanced search interface (Implemented via AI chat commands for notes)
    *   [x] Tag filtering (Implicitly via AI `find_notes` by tags)
    *   [ ] Date range filtering
    *   [x] Search results display (In chat as AI feedback and updated `NoteList`)

3.  **Settings Management**
    *   [ ] User settings interface
    *   [ ] Export/import functionality
    *   [ ] Theme customization
    *   [ ] AI preferences

4.  **AI Integration**
    *   [x] Chat interface (`ChatInterface.tsx` implemented with message display, input, AI context history)
    *   [x] Real-time response handling (WebSocket communication established)
    *   [x] Command history (User queries and AI responses displayed in chat, AI context history in `NoteList`)
    *   [x] Error handling (WebSocket errors, AI processing errors reported in chat)
    *   [x] AI Help Command (`show_help` intent implemented, `KIT_AI_HELP_MESSAGE` served)
    *   [x] Conversation History for AI (Frontend sends history, backend formats for Gemini)
    *   [x] AI Note Content Updates (`update_note_content` intent implemented)
    *   [x] Multiple Deletions (`delete_note` intent handles list of IDs)

5.  **AI Chat Agent Enhancements (Parity with Old Version & New Ideas)**
    *   [x] **Date Range Search:** Implement AI intent and backend logic for `find_notes` to support date range filtering (e.g., "find notes from last week").
    *   [x] **Note Properties Update via AI:** Design an AI intent (e.g., `update_note_properties`) and backend logic to allow updating a note's `properties_json` field via chat.
    *   [ ] **Remove Tags via AI:** Implement AI intent (e.g., `remove_tags_from_note`) and backend logic for removing one or more tags from a note.
    *   [ ] **List All Tags via AI:** Implement AI intent (e.g., `list_all_tags`) and backend logic to display all unique tags in the system.
    *   [ ] **Restore Note via AI:** Implement AI intent (e.g., `restore_note`) and backend logic to restore a soft-deleted note.
    *   [ ] **List Deleted Notes via AI:** Implement AI intent (e.g., `list_deleted_notes`) and backend logic.
    *   [ ] **Restore Deleted Notes via AI:** The ability to restore / un-soft delete the soft deleted notes
    *   [ ] **View Note Version History via AI:** Design an AI intent (e.g., `get_note_history`) for the AI to trigger display/summary of a note's version history (frontend will still need its version history viewer component).
    *   [ ] **Data Export/Import via AI:** Consider if AI-driven export/import is desired (e.g., "export my notes"). This might be lower priority if UI buttons are preferred.
    *   [ ] **Settings Management via AI:** Allow users to get/set some basic settings via chat (e.g., "what's my user name?", "set my user name to X").

### Phase 4: Polish and Optimization (1 week)

1.  **Performance Optimization**
    *   [ ] Code splitting
    *   [ ] Lazy loading
    *   [ ] Caching strategies
    *   [ ] Bundle optimization

2.  **UI/UX Improvements**
    *   [ ] Animations and transitions
    *   [x] Loading states (Implemented for notes and chat)
    *   [x] Error states (Implemented for notes and chat)
    *   [x] Responsive design (Basic responsiveness, MUI aids this; independent column scrolling in `App.tsx`)
    *   [x] Chat Interface Compactness (Margins, padding, list rendering adjusted)
    *   [x] Edge-to-Edge Width (Layout issues in `index.css` and `App.tsx` resolved)

3.  **Testing and Documentation**
    *   [ ] Unit tests (Backend tests copied and path-adjusted: `test_note_tool.py`, `test_settings_tool.py`)
    *   [ ] Integration tests
    *   [x] API documentation (FastAPI `/docs` provides this automatically)
    *   [ ] User documentation (To be created)

4.  **Deployment Preparation**
    *   [x] Environment configuration (`.env.example` was mentioned, actual may vary)
    *   [x] Build scripts (`restart_dev_servers.ps1` refined)
    *   [ ] Deployment documentation
    *   [ ] Monitoring setup

## Technical Specifications

### Backend (Python)

1. **API Framework**
   - [x] FastAPI for REST API
   - [x] WebSocket support for real-time AI
   - [ ] JWT authentication
   - [ ] Rate limiting

2. **Database**
   - [x] SQLite (development)
   - [ ] PostgreSQL (production)
   - [x] Connection pooling
   - [x] Migration system

3. **AI Integration**
   - [x] Modified KIT.py as a service (Handled via `ai_service.py` and `KIT` module)
   - [x] WebSocket support
   - [x] Error handling
   - [x] Logging (Advanced rotating file logs implemented)

### Frontend (React)

1. **Core Technologies**
   - [x] React 18
   - [x] TypeScript
   - [x] Vite
   - [x] Material-UI/Tailwind CSS (MUI chosen and implemented)

2. **State Management**
   - [x] Redux Toolkit/Context API (Redux Toolkit chosen)
   - [ ] React Query for API data (Using Redux Thunks for now)
   - [ ] Local storage persistence

3. **UI Components**
   - [x] Material-UI components
   - [x] Custom components (`