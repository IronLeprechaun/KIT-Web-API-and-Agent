# KIT_Web: AI-Powered Note Management System

KIT_Web is a web application that combines a Python FastAPI backend with a React frontend to provide an AI-driven note management system. It leverages Google's Gemini for natural language processing to create, find, update, and manage notes through a chat interface.

## Project Structure

```
KIT_Web/
├── backend/          # Python FastAPI backend
│   ├── KITCore/      # Core note and settings logic
│   ├── KIT/          # AI agent and Gemini client
│   ├── api/          # FastAPI app, routes, services
│   ├── logs/         # Rotated log files
│   ├── config.py     # Backend configuration
│   └── ...
├── frontend/         # React (Vite + TypeScript) frontend
│   ├── src/
│   │   ├── components/
│   │   ├── stores/
│   │   └── ...
│   └── ...
├── scripts/          # Testing and server management scripts
│   ├── test_runner.py
│   ├── server_manager.py
│   └── ...
├── tests/            # Test suites
│   ├── database/     # Database tests
│   ├── api/          # API endpoint tests
│   └── ...
├── requirements-testing.txt  # Testing dependencies
├── package.json      # Frontend dependencies
├── package-lock.json
├── node_modules/     # Frontend node modules
├── DOCUMENTATION.md  # Technical documentation
├── README.md         # This file
└── restart_dev_servers.ps1  # PowerShell script to restart dev servers
```

For a more detailed project structure, see the `KIT_WEB_CONVERSION_PLAN.md`.

## Features

*   **AI-Powered Chat Interface:** Interact with your notes using natural language.
    *   Create new notes.
    *   Find notes by content, tags, or ID.
    *   Update note content.
    *   Add tags to notes.
    *   Delete notes (single or multiple).
    *   View AI command history.
    *   Get help on available AI commands.
*   **Note Listing:** View all your notes in a separate panel.
*   **FastAPI Backend:** Robust and modern Python backend.
*   **React Frontend:** Responsive and interactive user interface using MUI and Redux Toolkit.
*   **Advanced Logging:** Rotating log files for both backend API and AI services.

## Prerequisites

*   Python 3.11+
*   Node.js (latest LTS version recommended)
*   PowerShell (for using the `restart_dev_servers.ps1` script on Windows)
*   A Google AI API Key for Gemini (stored securely using our encrypted secrets manager)

## 🔐 Secure API Key Setup (REQUIRED FIRST STEP)

Before setting up the backend, you must securely store your API keys using our encrypted secrets manager:

```bash
# Navigate to the project directory
cd KIT_Web

# Set up secure secrets (interactive wizard)
python scripts/secrets_manager.py --setup
```

This will:
1. 🔑 Prompt you to create a master password
2. 🔐 Encrypt and store your API keys locally
3. 🚫 Ensure keys are NEVER committed to git
4. 📁 Create secure `.secrets/` directory (git-ignored)

**Why this approach?**
- ✅ **Secure**: AES encryption with PBKDF2 key derivation
- ✅ **Local**: Keys stay on your machine, never in git
- ✅ **Convenient**: Automatic integration with development tools
- ✅ **Safe**: Comprehensive .gitignore protection

## Backend Setup (`KIT_Web/backend/`)

1.  **Navigate to the backend directory:**
    ```bash
    cd KIT_Web/backend
    ```

2.  **Create and activate a virtual environment:**
    ```bash
    python -m venv .venv
    # On Windows (PowerShell)
    .\.venv\Scripts\Activate.ps1
    # On macOS/Linux
    # source .venv/bin/activate
    ```

3.  **Install dependencies:**
    ```bash
    pip install -r api/requirements.txt
    ```

4.  **Set up environment variables using secure secrets:**
    *   **IMPORTANT**: Use the secure secrets manager instead of plain environment variables:
    ```bash
    # Set up your API keys securely
    cd KIT_Web
    python scripts/secrets_manager.py --setup
    ```
    *   The backend uses a `config.py` file (`KIT_Web/backend/config.py`) for settings like database path and default log level. Review and adjust if necessary.

5.  **Database Migrations (Alembic):**
    *   The database (`kit_agent.db`) will be created in `KIT_Web/backend/KITCore/database/`.
    *   To apply migrations (if any new ones are added):
        ```bash
        cd api # Navigate to where alembic.ini is
        alembic upgrade head
        cd .. # Go back to backend directory
        ```

6.  **Run the backend server:**
    *   From the `KIT_Web/backend/` directory:
        ```bash
        uvicorn api.app:app --reload --port 8000
        ```
    *   The API will be available at `http://localhost:8000`.
    *   API documentation (Swagger UI) will be at `http://localhost:8000/docs`.

## Frontend Setup (`KIT_Web/frontend/`)

1.  **Navigate to the frontend directory:**
    ```bash
    cd KIT_Web/frontend
    ```

2.  **Install dependencies:**
    ```bash
    npm install
    ```

3.  **Run the frontend development server:**
    ```bash
    npm run dev
    ```
    *   The React app will be available at `http://localhost:5173` (or another port if 5173 is busy).

## Running Both Servers (Development)

The `restart_dev_servers.ps1` script in the project root can be used on Windows (with PowerShell) to stop any existing instances and restart both the backend and frontend development servers.

1.  Ensure the script has execution permissions: `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass` (if needed).
2.  Run the script from the project root (`D:/_Programming/Python KIT System/`):
    ```powershell
    ./restart_dev_servers.ps1
    ```

## Logging

*   Backend API logs are stored in `KIT_Web/backend/logs/backend_api_*.log`.
*   AI service logs are stored in `KIT_Web/backend/logs/kit_agent_*.log` and `kit_trace_*.log`.
*   Log rotation is implemented to manage file sizes and counts. See `KIT_Web/backend/api/config_settings.py` for rotation settings.

## 🚀 Development Tools & Automation

KIT_Web includes comprehensive development tools that make coding and updating much easier:

### Quick Start Commands

```bash
# Set up development environment (first time)
cd KIT_Web && python scripts/dev_setup.py --setup-all

# Daily development workflow
cd KIT_Web && python scripts/server_manager.py --start-all
cd KIT_Web && python scripts/enhanced_tester.py --comprehensive
```

### Available Development Tools

- **`dev_setup.py`** - Environment setup & dependency management
- **`config_manager.py`** - Environment configurations & .env management  
- **`enhanced_tester.py`** - Comprehensive testing with detailed reporting
- **`log_analyzer.py`** - Smart log analysis & debugging assistance
- **`server_manager.py`** - Server lifecycle & health monitoring

### Testing Framework

```bash
# Comprehensive testing (recommended)
cd KIT_Web && python scripts/enhanced_tester.py --comprehensive

# Individual test suites
cd KIT_Web && python scripts/enhanced_tester.py --database
cd KIT_Web && python scripts/enhanced_tester.py --backend
cd KIT_Web && python scripts/enhanced_tester.py --api
cd KIT_Web && python scripts/enhanced_tester.py --performance

# Health checks & server management
cd KIT_Web && python scripts/server_manager.py --health-check
cd KIT_Web && python scripts/server_manager.py --start-all
```

### Debugging & Troubleshooting

```bash
# Analyze recent errors
cd KIT_Web && python scripts/log_analyzer.py --errors

# Check system configuration  
cd KIT_Web && python scripts/config_manager.py --check

# Reset database if needed
cd KIT_Web && python scripts/dev_setup.py --reset-db
```

📖 **Complete Guide**: See [DEVELOPMENT_TOOLS.md](DEVELOPMENT_TOOLS.md) for detailed workflows, usage examples, and troubleshooting guides.

---

This README provides a starting point. For more in-depth information on architecture, conversion phases, and specific component details, please refer to `DOCUMENTATION.md` and `KIT_WEB_CONVERSION_PLAN.md`. 