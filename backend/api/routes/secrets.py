"""
Secrets Management API Routes
Provides secure API endpoints for managing encrypted secrets via the UI.
"""

from fastapi import APIRouter, HTTPException, Body, Depends
from fastapi.security import HTTPBearer
from pydantic import BaseModel
from typing import Dict, List, Optional
import sys
import os
from pathlib import Path

# Add scripts directory to path so we can import our secrets manager
sys.path.append(str(Path(__file__).parent.parent.parent.parent / "scripts"))

try:
    from secrets_manager import SecretsManager
    SECRETS_AVAILABLE = True
except ImportError:
    SECRETS_AVAILABLE = False

router = APIRouter(prefix="/secrets", tags=["secrets"])
security = HTTPBearer(auto_error=False)

# Pydantic models for API requests/responses
class SecretRequest(BaseModel):
    key: str
    value: str

class SecretGetRequest(BaseModel):
    key: str

class SecretDeleteRequest(BaseModel):
    key: str

class SecretsListRequest(BaseModel):
    pass  # No fields needed for local app

class SecretResponse(BaseModel):
    success: bool
    message: str
    data: Optional[Dict] = None

class SecretsStatusResponse(BaseModel):
    secrets_available: bool
    config_exists: bool
    secrets_count: int
    secrets_keys: List[str] = []

@router.get("/status", response_model=SecretsStatusResponse)
async def get_secrets_status():
    """Get the current status of the secrets management system"""
    if not SECRETS_AVAILABLE:
        return SecretsStatusResponse(
            secrets_available=False,
            config_exists=False,
            secrets_count=0,
            secrets_keys=[]
        )
    
    try:
        manager = SecretsManager()
        secrets_file_exists = manager.secrets_file.exists()
        
        if secrets_file_exists:
            try:
                secrets = manager.load_secrets()
                user_secrets = {k: v for k, v in secrets.items() if not k.startswith("_")}
                return SecretsStatusResponse(
                    secrets_available=True,
                    config_exists=True,
                    secrets_count=len(user_secrets),
                    secrets_keys=list(user_secrets.keys())
                )
            except:
                return SecretsStatusResponse(
                    secrets_available=True,
                    config_exists=True,
                    secrets_count=0,
                    secrets_keys=[]
                )
        else:
            return SecretsStatusResponse(
                secrets_available=True,
                config_exists=False,
                secrets_count=0,
                secrets_keys=[]
            )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error checking secrets status: {str(e)}")

@router.post("/set", response_model=SecretResponse)
async def set_secret(request: SecretRequest):
    """Set a secret value"""
    if not SECRETS_AVAILABLE:
        raise HTTPException(status_code=503, detail="Secrets manager not available")
    
    try:
        manager = SecretsManager()
        success = manager.set_secret(request.key, request.value)
        
        if success:
            return SecretResponse(
                success=True,
                message=f"Secret '{request.key}' saved successfully"
            )
        else:
            return SecretResponse(
                success=False,
                message=f"Failed to save secret '{request.key}'"
            )
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error setting secret: {str(e)}")

@router.post("/get", response_model=SecretResponse)
async def get_secret(request: SecretGetRequest):
    """Get a secret value"""
    if not SECRETS_AVAILABLE:
        raise HTTPException(status_code=503, detail="Secrets manager not available")
    
    try:
        manager = SecretsManager()
        value = manager.get_secret(request.key)
        
        if value is not None:
            return SecretResponse(
                success=True,
                message=f"Secret '{request.key}' retrieved successfully",
                data={"key": request.key, "value": value}
            )
        else:
            return SecretResponse(
                success=False,
                message=f"Secret '{request.key}' not found"
            )
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error retrieving secret: {str(e)}")

@router.get("/list", response_model=SecretResponse)
async def list_secrets():
    """List all secret keys (not values)"""
    if not SECRETS_AVAILABLE:
        raise HTTPException(status_code=503, detail="Secrets manager not available")
    
    try:
        manager = SecretsManager()
        secrets = manager.load_secrets()
        
        # Filter out internal setup markers
        user_secrets = {k: v for k, v in secrets.items() if not k.startswith("_")}
        
        return SecretResponse(
            success=True,
            message="Secrets listed successfully",
            data={"keys": list(user_secrets.keys()), "count": len(user_secrets)}
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error listing secrets: {str(e)}")

@router.delete("/delete/{key}", response_model=SecretResponse)
async def delete_secret(key: str):
    """Delete a secret"""
    if not SECRETS_AVAILABLE:
        raise HTTPException(status_code=503, detail="Secrets manager not available")
    
    try:
        manager = SecretsManager()
        success = manager.delete_secret(key)
        
        if success:
            return SecretResponse(
                success=True,
                message=f"Secret '{key}' deleted successfully"
            )
        else:
            return SecretResponse(
                success=False,
                message=f"Secret '{key}' not found"
            )
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error deleting secret: {str(e)}")

@router.post("/setup", response_model=SecretResponse)
async def setup_secrets():
    """Initialize the secrets system"""
    if not SECRETS_AVAILABLE:
        raise HTTPException(status_code=503, detail="Secrets manager not available")
    
    try:
        manager = SecretsManager()
        # Just ensure the secrets directory exists
        manager.secrets_dir.mkdir(exist_ok=True)
        
        return SecretResponse(
            success=True,
            message="Secrets system initialized successfully"
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error initializing secrets: {str(e)}") 