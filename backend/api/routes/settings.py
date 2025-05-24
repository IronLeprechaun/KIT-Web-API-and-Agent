from fastapi import APIRouter, HTTPException, Depends, Body
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, validator
from ..auth_utils import get_current_user # New import
import sys
import os

# Adjust path to import SettingService
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..')) # Add backend directory to sys.path
from api.services.settings_service import SettingsService
from KITCore.tools.settings_tool import DEFAULT_SETTINGS # For validation and defaults

router = APIRouter(
    prefix="/settings",
    tags=["settings"],
    # dependencies=[Depends(get_current_user)] # Temporarily disabled for testing
)

# Pydantic Models for Settings
class SettingItem(BaseModel):
    key: str
    value: Any

    @validator('key')
    def key_must_be_valid(cls, v):
        if v not in DEFAULT_SETTINGS:
            raise ValueError(f"Invalid setting key: {v}. Allowed keys are: {list(DEFAULT_SETTINGS.keys())}")
        return v
    
    # Further validation for value based on key type could be added here or in the service layer

class SettingsList(BaseModel):
    settings: Dict[str, Any]

# Settings Service Instance
settings_service = SettingsService()

@router.get("/", response_model=SettingsList, summary="List all current configuration settings and their values")
async def list_settings_endpoint():
    try:
        all_settings = await settings_service.get_all_settings()
        return SettingsList(settings=all_settings)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to retrieve settings: {str(e)}")

@router.get("/{key}", response_model=SettingItem, summary="Get the value of a specific configuration setting")
async def get_setting_endpoint(key: str):
    try:
        value = await settings_service.get_setting(key)
        if value is None: # Check if setting exists (KITCore might return None for non-existent keys)
            raise HTTPException(status_code=404, detail=f"Setting key '{key}' not found.")
        return SettingItem(key=key, value=value)
    except ValueError as ve: # Catch validation errors from Pydantic model or service
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to retrieve setting '{key}': {str(e)}")

@router.put("/", response_model=SettingItem, summary="Set the value of a configuration setting")
async def set_setting_endpoint(setting: SettingItem = Body(...)):
    try:
        # The SettingItem model already validates the key.
        # Additional type validation for the value might be needed here or in the service.
        updated_value = await settings_service.set_setting(setting.key, setting.value)
        return SettingItem(key=setting.key, value=updated_value) # Return the successfully set key-value
    except ValueError as ve: # Catch validation errors
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to set setting '{setting.key}': {str(e)}")

@router.delete("/{key}", summary="Delete a configuration setting, reverting it to its default value")
async def delete_setting_endpoint(key: str):
    try:
        if key not in DEFAULT_SETTINGS:
            raise HTTPException(status_code=400, detail=f"Invalid setting key: {key}")
        
        await settings_service.delete_setting(key)
        # After deletion, KITCore's get_setting usually returns the default value.
        # So, we fetch and return that to confirm.
        default_value = await settings_service.get_setting(key) 
        return {"message": f"Setting '{key}' deleted and reverted to default.", "key": key, "new_value": default_value}
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete setting '{key}': {str(e)}") 