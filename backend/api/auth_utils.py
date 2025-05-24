from fastapi import HTTPException, Depends
from fastapi.security import OAuth2PasswordBearer
from typing import Optional
from jose import JWTError, jwt
from pydantic import BaseModel
import os
from dotenv import load_dotenv
from datetime import datetime, timedelta # Ensure timedelta is imported if create_access_token is also moved

# Load environment variables if SECRET_KEY is sourced from here
# load_dotenv() # Or ensure it's loaded in app.py and SECRET_KEY is passed around or globally accessible

# Configuration (can be loaded from app.py or a shared config module)
SECRET_KEY = os.getenv("SECRET_KEY", "your-secret-key-here") # Ensure this is consistent
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", 30))

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token") # tokenUrl might be defined in app.py (e.g. /api/v1/token)

class TokenData(BaseModel):
    username: Optional[str] = None

# Potentially move create_access_token here as well if it makes sense
# def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
#     to_encode = data.copy()
#     if expires_delta:
#         expire = datetime.utcnow() + expires_delta
#     else:
#         expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
#     to_encode.update({"exp": expire})
#     encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
#     return encoded_jwt

async def get_current_user(token: str = Depends(oauth2_scheme)) -> TokenData:
    credentials_exception = HTTPException(
        status_code=401, # Corrected from status.HTTP_401_UNAUTHORIZED if status wasn't imported
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: Optional[str] = payload.get("sub")
        if username is None:
            raise credentials_exception
        token_data = TokenData(username=username)
    except JWTError:
        raise credentials_exception
    return token_data 