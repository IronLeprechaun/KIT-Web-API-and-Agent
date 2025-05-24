import logging
import os
from datetime import datetime, timedelta
import glob
from typing import Optional
import sys

# General Project Structure Assumptions for Logging:
# - A central `config.py` exists in the `backend` directory.
# - Logs are stored in a `logs` directory also within the `backend` directory.

# For this project, config is expected to be in backend/config.py
# This logger_utils is inside backend/KIT/
# So it should find backend/config.py via relative pathing or if backend dir is in sys.path

# To access DEFAULT_LOG_LEVEL from backend/config.py:
# One way is to ensure backend is in sys.path when this module is loaded.
# AIService.py which calls this, already adds its parent's parent (backend) to sys.path.

try:
    # DEFAULT_LOG_LEVEL comes from the main backend config
    from backend.config import DEFAULT_LOG_LEVEL
    # MAX_LOG_SIZE_MB and the specific MAX_AISERVICE_LOG_FILES come from api.config_settings
    from api.config_settings import MAX_LOG_SIZE_MB, MAX_AISERVICE_LOG_FILES as MAX_LOG_FILES
except ImportError as e:
    # This fallback is primarily for standalone testing of logger_utils or if config is not found.
    print(f"logger_utils: Could not import logging settings from config: {e}. Using default logging settings.", file=sys.stderr)
    DEFAULT_LOG_LEVEL = "INFO" # Fallback
    MAX_LOG_SIZE_MB = 10       # Fallback
    MAX_LOG_FILES = 5          # Fallback

LOG_LEVEL_MAP = {
    "DEBUG": logging.DEBUG,
    "INFO": logging.INFO,
    "WARNING": logging.WARNING,
    "ERROR": logging.ERROR,
    "CRITICAL": logging.CRITICAL
}

def setup_kit_loggers(run_timestamp_str: str, trace_enabled_for_session: bool, max_log_files: Optional[int] = None):
    """Configures and returns the kit_agent_logger and kit_trace_logger."""
    logs_dir = os.path.join(os.path.dirname(__file__), "..", "logs") # logs relative to backend/
    os.makedirs(logs_dir, exist_ok=True)

    # --- Log rotation/cleanup for kit_agent logs ---
    if max_log_files is not None and max_log_files > 0: # Ensure max_log_files is a positive number
        agent_log_pattern = os.path.join(logs_dir, "kit_agent_*.log")
        existing_agent_logs = sorted(
            glob.glob(agent_log_pattern),
            key=os.path.getmtime # Oldest first
        )

        # Calculate how many files to delete
        # We want to make space if the current number of logs plus the new one will exceed the max
        num_existing = len(existing_agent_logs)
        
        # Number of files to delete if, after adding the new one, we'd be over the limit.
        # Or if we are already at the limit, we delete the oldest to make space.
        if num_existing >= max_log_files:
            files_to_delete_count = (num_existing - max_log_files) + 1
            
            # Ensure we don't try to delete more files than exist
            files_to_delete_count = min(files_to_delete_count, num_existing)

            for i in range(files_to_delete_count):
                try:
                    os.remove(existing_agent_logs[i]) # Remove the oldest ones
                    print(f"LOG UTIL: Removed old agent log file: {existing_agent_logs[i]}", file=sys.stderr) 
                except OSError as e:
                    print(f"LOG UTIL ERROR: Error removing old agent log file {existing_agent_logs[i]}: {e}", file=sys.stderr)

    # --- Kit Agent Logger (Normal) ---
    agent_logger = logging.getLogger("KIT_Agent")
    agent_log_level_str = DEFAULT_LOG_LEVEL.upper()
    agent_log_level = LOG_LEVEL_MAP.get(agent_log_level_str, logging.INFO)
    agent_logger.setLevel(agent_log_level)

    # Clear existing handlers for KIT_Agent to prevent duplicate logging if re-initialized
    if agent_logger.hasHandlers():
        agent_logger.handlers.clear()

    agent_log_file = os.path.join(logs_dir, f"kit_agent_{run_timestamp_str}.log")
    agent_handler = logging.FileHandler(agent_log_file, mode='w')
    agent_formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    agent_handler.setFormatter(agent_formatter)
    agent_logger.addHandler(agent_handler)
    
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(agent_formatter)
    console_handler.setLevel(agent_log_level)
    agent_logger.addHandler(console_handler)

    agent_logger.info(f"Agent logger initialized. Level: {agent_log_level_str}. File: {agent_log_file}")

    # --- Kit Trace Logger (Detailed) ---
    trace_logger = None
    if trace_enabled_for_session:
        trace_logger = logging.getLogger("KIT_Trace")
        trace_logger.setLevel(logging.DEBUG)

        if trace_logger.hasHandlers():
            trace_logger.handlers.clear()
            
        trace_log_file = os.path.join(logs_dir, f"kit_trace_{run_timestamp_str}.log")
        trace_handler = logging.FileHandler(trace_log_file, mode='w')
        trace_formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(module)s:%(funcName)s:%(lineno)d - %(message)s')
        trace_handler.setFormatter(trace_formatter)
        trace_logger.addHandler(trace_handler)
        trace_logger.info(f"Trace logger initialized. Level: DEBUG. File: {trace_log_file}")
        agent_logger.info("Trace logging is ENABLED for this session.")
    else:
        agent_logger.info("Trace logging is DISABLED for this session.")

    return agent_logger, trace_logger

# Example usage for testing the logger setup
# (This part might not run correctly without adjusting sys.path if run directly from here)
if __name__ == '__main__':
    print("Testing logger setup directly from logger_utils.py...")
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    # Adjust sys.path for standalone testing to find config.py
    # This assumes logger_utils.py is in backend/KIT/
    # and config.py is in backend/

    current_script_dir = os.path.dirname(os.path.abspath(__file__))
    backend_dir_for_test = os.path.dirname(current_script_dir) # Up to backend/
    if backend_dir_for_test not in sys.path:
        sys.path.insert(0, backend_dir_for_test)
    print(f"backend_dir_for_test: {backend_dir_for_test}, sys.path: {sys.path}")

    try:
        from config import DEFAULT_LOG_LEVEL as CONFIG_DEFAULT_LOG_LEVEL
        print(f"Successfully imported CONFIG_DEFAULT_LOG_LEVEL: {CONFIG_DEFAULT_LOG_LEVEL} for direct test.")
    except ImportError:
        print("LOG UTIL TEST ERROR: Could not import config for direct test. Ensure config.py is in backend.")
        CONFIG_DEFAULT_LOG_LEVEL = "INFO" # Fallback for test

    logger = setup_logger("TestLogger", "test_log_utils.log", level=CONFIG_DEFAULT_LOG_LEVEL)

    print("\n--- Test 1: Trace Disabled, Max Logs 2 ---")
    # Create dummy old log files for cleanup test
    temp_logs_dir = os.path.join(backend_dir_for_test, "logs")
    os.makedirs(temp_logs_dir, exist_ok=True)
    for i in range(3):
        with open(os.path.join(temp_logs_dir, f"kit_agent_old_log_{i}.log"), 'w') as f:
            f.write("old log content")
        # Vary modification times slightly for sort order
        if os.path.exists(os.path.join(temp_logs_dir, f"kit_agent_old_log_{i}.log")):
             os.utime(os.path.join(temp_logs_dir, f"kit_agent_old_log_{i}.log"), (datetime.now() - timedelta(seconds=10-i)).timestamp(), (datetime.now() - timedelta(seconds=10-i)).timestamp())


    agent_log, trace_log = setup_kit_loggers(f"{ts}_test1", trace_enabled_for_session=False, max_log_files=2)
    agent_log.debug("This is an agent debug message (should not appear if level is INFO).")
    agent_log.info("This is an agent info message.")
    agent_log.warning("This is an agent warning message.")
    if trace_log:
        trace_log.debug("This is a trace debug message (should not appear as trace_log is None).")
    else:
        print("Trace log is None, as expected.")

    print("\n--- Test 2: Trace Enabled, Max Logs 1 ---")
    agent_log2, trace_log2 = setup_kit_loggers(f"{ts}_test2", trace_enabled_for_session=True, max_log_files=1)
    agent_log2.info("This is another agent info message.")
    if trace_log2:
        trace_log2.debug("This is a trace debug message (should appear).")
        trace_log2.info("This is a trace info message (should appear).")
    else:
        print("Trace log is None, which is UNEXPECTED here.")
    
    print(f"\nCheck the '{temp_logs_dir}' directory for output files.") 