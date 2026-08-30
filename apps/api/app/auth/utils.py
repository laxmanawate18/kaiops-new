import os
import uuid
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any
from jose import JWTError, jwt
from passlib.context import CryptContext
from fastapi import HTTPException, status
from .models import UserRole
from .token_blacklist import is_revoked as _is_token_revoked
import secrets
import hashlib

logger = logging.getLogger(__name__)

# Configuration
SECRET_KEY = os.getenv("SECRET_KEY")
if not SECRET_KEY:
    if os.getenv("SECRET_KEY_INSECURE_DEV", "").lower() == "true":
        # Dev-only escape hatch: stable key so tokens survive restarts in local dev.
        SECRET_KEY = "insecure-dev-secret-key-do-not-use-in-production"
        logger.warning(
            "SECRET_KEY is not set — using INSECURE dev fallback key because "
            "SECRET_KEY_INSECURE_DEV=true. NEVER enable this in production!"
        )
    else:
        raise RuntimeError(
            "SECRET_KEY environment variable is required. "
            "Generate one with: python -c \"import secrets; print(secrets.token_urlsafe(32))\""
        )
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30
REFRESH_TOKEN_EXPIRE_DAYS = 7

# Use Argon2 instead of bcrypt - no 72-byte limit and more secure
pwd_context = CryptContext(
    schemes=["argon2", "bcrypt"],  # Argon2 first, bcrypt as fallback
    deprecated="auto",
    argon2__memory_cost=65536,     # 64 MB
    argon2__time_cost=3,           # 3 iterations
    argon2__parallelism=1,         # 1 thread
)

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against its hash."""
    try:
        return pwd_context.verify(plain_password, hashed_password)
    except Exception as e:
        print(f"Password verification error: {e}")
        return False

def get_password_hash(password: str) -> str:
    """Hash a password using Argon2."""
    try:
        return pwd_context.hash(password)
    except Exception as e:
        print(f"Password hashing error: {e}")
        raise ValueError("Password hashing failed")

def create_access_token(data: Dict[str, Any], expires_delta: Optional[timedelta] = None) -> str:
    """Create a JWT access token."""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)

    to_encode.update({"exp": expire, "type": "access", "jti": str(uuid.uuid4())})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def create_refresh_token(username: str) -> str:
    """Create a JWT refresh token with a 7-day expiry."""
    expire = datetime.now(timezone.utc) + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    to_encode = {
        "sub": username,
        "exp": expire,
        "type": "refresh",
        "jti": str(uuid.uuid4()),
    }
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def get_jti(payload: Dict[str, Any]) -> Optional[str]:
    """Extract the jti (token ID) claim from a decoded payload."""
    return payload.get("jti")

def verify_token(token: str, expected_type: str = "access") -> Dict[str, Any]:
    """Verify and decode a JWT token.

    Checks the token type claim (refresh tokens cannot be used as access tokens
    and vice versa), and rejects revoked tokens (logout/blacklist).
    Tokens without a "type" claim (legacy) are treated as access tokens.
    """
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        role: str = payload.get("role")

        if username is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid authentication credentials",
                headers={"WWW-Authenticate": "Bearer"},
            )

        token_type = payload.get("type", "access")
        if token_type != expected_type:
            logger.warning(f"Token type mismatch: got '{token_type}', expected '{expected_type}'")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token type",
                headers={"WWW-Authenticate": "Bearer"},
            )

        jti = payload.get("jti")
        if jti and _is_token_revoked(jti):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token has been revoked",
                headers={"WWW-Authenticate": "Bearer"},
            )

        return {"username": username, "role": role}
    except HTTPException:
        raise
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
