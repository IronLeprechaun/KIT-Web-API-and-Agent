# config.py

import os

# Define the base directory of the project
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Define the database path relative to the base directory
# KIT_DATABASE_PATH = os.path.join(BASE_DIR, 'database', 'kit_agent.db')
# For simplicity during initial setup, let's place it in KITCore for now
KIT_DATABASE_DIR = os.path.join(BASE_DIR, 'KITCore', 'database')
KIT_DATABASE_NAME = 'kit_agent.db'
KIT_DATABASE_PATH = os.path.join(KIT_DATABASE_DIR, KIT_DATABASE_NAME)

# Ensure the database directory exists
# os.makedirs(KIT_DATABASE_DIR, exist_ok=True) # We'll handle directory creation in database_manager

# API keys are managed securely via the secrets manager (scripts/secrets_manager.py)
# Use: python scripts/secrets_manager.py --setup to configure API keys
# API keys are loaded dynamically by services that need them

# Default Logging Level for the agent
# Options: "DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"
DEFAULT_LOG_LEVEL = "INFO" 