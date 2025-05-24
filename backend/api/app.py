from fastapi import FastAPI, HTTPException, Depends, APIRouter
from fastapi.middleware.cors import CORSMiddleware
from typing import Optional
import uvicorn
from datetime import datetime, timedelta
from jose import JWTError, jwt
from pydantic import BaseModel
import os
from dotenv import load_dotenv
import logging
import logging.config
import glob # Added for log file management

# Import routers
from .routes import notes, tags, settings, ai, secrets

# Import MAX_BACKEND_LOG_FILES from new config
from .config_settings import MAX_BACKEND_LOG_FILES # Added

# Create logs directory if it doesn't exist
LOGS_DIR = "logs"
if not os.path.exists(LOGS_DIR):
    os.makedirs(LOGS_DIR)

# Logging Configuration
def setup_logging():
    # Generate a timestamped log file name
    current_time_str = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_filename = os.path.join(LOGS_DIR, f"backend_api_{current_time_str}.log")

    # --- Log rotation/cleanup ---
    # List existing backend_api log files
    existing_log_files = sorted(
        glob.glob(os.path.join(LOGS_DIR, "backend_api_*.log")),
        key=os.path.getmtime
    )
    
    # Remove oldest files if count exceeds MAX_BACKEND_LOG_FILES
    if len(existing_log_files) >= MAX_BACKEND_LOG_FILES: # Use >= to ensure current log is also counted if limit is small
        files_to_delete = len(existing_log_files) - MAX_BACKEND_LOG_FILES + 1 # +1 to make space for the new one
        for i in range(files_to_delete):
            if i < len(existing_log_files): # Ensure we don't try to delete more than exist
                try:
                    os.remove(existing_log_files[i])
                    logging.info(f"Removed old log file: {existing_log_files[i]}") # Use a basic log for this
                except OSError as e:
                    logging.error(f"Error removing old log file {existing_log_files[i]}: {e}")

    logging_config = {
        'version': 1,
        'disable_existing_loggers': False,
        'formatters': {
            'default': {
                'format': '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            },
        },
        'handlers': {
            'console': {
                'class': 'logging.StreamHandler',
                'formatter': 'default',
                'level': 'INFO',
            },
            'file': {
                'class': 'logging.FileHandler', # Changed from RotatingFileHandler
                'formatter': 'default',
                'filename': log_filename, # Use timestamped filename
                'level': 'INFO',
            },
        },
        'root': {
            'handlers': ['console', 'file'],
            'level': 'INFO',
        },
        'loggers': {
            'uvicorn.error': {
                'handlers': ['console', 'file'],
                'level': 'INFO',
                'propagate': False,
            },
            'uvicorn.access': {
                'handlers': ['console', 'file'],
                'level': 'INFO',
                'propagate': False,
            },
             'fastapi': {
                'handlers': ['console', 'file'],
                'level': 'INFO',
                'propagate': False,
            },
        }
    }
    logging.config.dictConfig(logging_config)

# Call logging setup
setup_logging()
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# Configuration
SECRET_KEY = os.getenv("SECRET_KEY", "your-secret-key-here")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", 30))

# Initialize FastAPI app
app = FastAPI(
    title="KIT Web API",
    description="API for KIT Web Application",
    version="1.0.0"
)

# Create a new main API router
api_router = APIRouter()

# Include individual routers into the main api_router
logger.info("Including notes router into api_router...")
api_router.include_router(notes.router)
logger.info("Notes router included into api_router.")

logger.info("Including tags router into api_router...")
api_router.include_router(tags.router)
logger.info("Tags router included into api_router.")

logger.info("Including settings router into api_router...")
api_router.include_router(settings.router)
logger.info("Settings router included into api_router.")

logger.info("Including ai router into api_router...")
api_router.include_router(ai.router)
logger.info("AI router included into api_router.")

logger.info("Including secrets router into api_router...")
api_router.include_router(secrets.router)
logger.info("Secrets router included into api_router.")

# Mount the main api_router with the /api prefix
app.include_router(api_router, prefix="/api")
logger.info("Main API router mounted at /api")

@app.on_event("startup")
async def startup_event():
    logger.info("Backend API starting up...")

@app.on_event("shutdown")
async def shutdown_event():
    logger.info("Backend API shutting down...")

# CORS middleware configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, replace with specific origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Pydantic models for request/response
class Token(BaseModel):
    access_token: str
    token_type: str

# Authentication functions
def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

# Root endpoint
@app.get("/")
async def root():
    return {"message": "Welcome to KIT Web API"}

# Health check endpoint
@app.get("/health")
async def health_check():
    return {"status": "healthy", "timestamp": datetime.utcnow()}

if __name__ == "__main__":
    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=True) 