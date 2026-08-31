from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPBearer
from datetime import timedelta
from typing import List
from .models import UserLogin, UserCreate, UserResponse, Token, PasswordChange, UserRole, UserUpdate, RefreshTokenRequest
from .database_firestore import user_db
from .utils import (
    verify_password,
    create_access_token,
    create_refresh_token,
    verify_token,
    get_jti,
    ACCESS_TOKEN_EXPIRE_MINUTES,
    REFRESH_TOKEN_EXPIRE_DAYS,
    ALGORITHM,
    SECRET_KEY,
)
from .token_blacklist import revoke as revoke_token
from jose import jwt
from .dependencies import get_current_user, get_current_admin_user
import logging

logger = logging.getLogger(__name__)
router = APIRouter()
security = HTTPBearer()

@router.post("/login", response_model=Token)
async def login(user_credentials: UserLogin):
    """Authenticate user and return access token."""
    try:
        user = user_db.get_user(user_credentials.username)
        
        if not user or not verify_password(user_credentials.password, user["password_hash"]):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect username or password",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        if not user["is_active"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Inactive user"
            )
        
        access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
        access_token = create_access_token(
            data={"sub": user["username"], "role": user["role"]},
            expires_delta=access_token_expires
        )
        refresh_token = create_refresh_token(user["username"])

        user_response = UserResponse(
            id=user["id"],
            username=user["username"],
            email=user["email"],
            full_name=user["full_name"],
            role=user["role"],
            is_active=user["is_active"],
            created_at=user["created_at"]
        )

        return Token(
            access_token=access_token,
            token_type="bearer",
            expires_in=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
            user=user_response,
            refresh_token=refresh_token
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Login error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Login failed"
        )

@router.post("/refresh", response_model=Token)
async def refresh(body: RefreshTokenRequest):
    """Exchange a valid refresh token for a new access + refresh token pair."""
    try:
        payload = jwt.decode(body.refresh_token, SECRET_KEY, algorithms=[ALGORITHM])
        username = payload.get("sub")

        if not username:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid refresh token",
                headers={"WWW-Authenticate": "Bearer"},
            )

        # Verify type claim and blacklist (legacy tokens without "type" are treated as access,
        # so they will be rejected here — refresh tokens must carry type="refresh").
        verify_token(body.refresh_token, expected_type="refresh")

        user = user_db.get_user(username)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found",
                headers={"WWW-Authenticate": "Bearer"},
            )
        if not user["is_active"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Inactive user"
            )

        # Rotate: revoke the used refresh token and issue a fresh pair.
        jti = get_jti(payload)
        if jti:
            revoke_token(jti, payload["exp"])

        access_token = create_access_token(
            data={"sub": user["username"], "role": user["role"]},
            expires_delta=timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
        )
        new_refresh_token = create_refresh_token(user["username"])

        user_response = UserResponse(
            id=user["id"],
            username=user["username"],
            email=user["email"],
            full_name=user["full_name"],
            role=user["role"],
            is_active=user["is_active"],
            created_at=user["created_at"]
        )

        return Token(
            access_token=access_token,
            token_type="bearer",
            expires_in=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
            user=user_response,
            refresh_token=new_refresh_token
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Token refresh error: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token",
            headers={"WWW-Authenticate": "Bearer"},
        )

@router.post("/logout")
async def logout(
    credentials=Depends(security),
    current_user: UserResponse = Depends(get_current_user)
):
    """Revoke the presented access token (logout)."""
    try:
        payload = jwt.decode(credentials.credentials, SECRET_KEY, algorithms=[ALGORITHM])
        jti = get_jti(payload)
        exp = payload.get("exp")
        if jti and exp:
            revoke_token(jti, exp)
        return {"message": "Logged out successfully"}
    except Exception as e:
        logger.error(f"Logout error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Logout failed"
        )

@router.post("/register", response_model=UserResponse)
async def register(
    user_data: UserCreate,
    current_user: UserResponse = Depends(get_current_admin_user)
):
    """Register a new user (Admin only)."""
    try:
        user = user_db.create_user(
            username=user_data.username,
            email=user_data.email,
            password=user_data.password,
            full_name=user_data.full_name
        )
        
        return UserResponse(
            id=user["id"],
            username=user["username"],
            email=user["email"],
            full_name=user["full_name"],
            role=user["role"],
            is_active=user["is_active"],
            created_at=user["created_at"]
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Registration error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Registration failed"
        )

@router.post("/change-password")
async def change_password(
    password_data: PasswordChange,
    current_user: UserResponse = Depends(get_current_user)
):
    """Change user password."""
    try:
        user = user_db.get_user(current_user.username)
        
        if not verify_password(password_data.current_password, user["password_hash"]):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Incorrect current password"
            )
        
        if not user_db.change_password(current_user.username, password_data.new_password):
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Password change failed"
            )

        return {"message": "Password changed successfully"}
    
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Password change error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Password change failed"
        )


# User routes
@router.get("/me", response_model=UserResponse)
async def get_current_user_info(current_user: UserResponse = Depends(get_current_user)):
    """Get current user information."""
    return current_user

# Admin routes
@router.get("/admin/users", response_model=List[UserResponse])
async def get_all_users(current_admin: UserResponse = Depends(get_current_admin_user)):
    """Get all users (admin only) with team information."""
    from .team_database_firestore import team_db
    
    users = user_db.get_all_users()
    user_responses = []
    
    for user in users:
        # Get user's teams
        user_teams = team_db.get_user_teams(user["id"])
        teams = [team["name"] for team in user_teams]
        team_lead_of = [team["name"] for team in user_teams if team.get("is_team_lead", False)]
        
        user_responses.append(
            UserResponse(
                id=user["id"],
                username=user["username"],
                email=user["email"],
                full_name=user["full_name"],
                role=user["role"],
                is_active=user["is_active"],
                created_at=user["created_at"],
                teams=teams,
                team_lead_of=team_lead_of
            )
        )
    
    return user_responses

@router.delete("/admin/users/{username}")
async def delete_user(
    username: str,
    current_admin: UserResponse = Depends(get_current_admin_user)
):
    """Delete a user (admin only)."""
    if username == current_admin.username:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete your own account"
        )
    
    if user_db.delete_user(username):
        return {"message": f"User {username} deleted successfully"}
    else:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )

@router.put("/admin/users/{username}/role")
async def update_user_role(
    username: str,
    role: UserRole,
    current_admin: UserResponse = Depends(get_current_admin_user)
):
    """Update user role (admin only)."""
    user = user_db.update_user(username, {"role": role})
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    return {"message": f"User {username} role updated to {role}"}

@router.put("/admin/users/{username}/toggle-active")
async def toggle_user_active(
    username: str,
    is_active: bool,
    current_admin: UserResponse = Depends(get_current_admin_user)
):
    """Toggle user active status (admin only)."""
    if username == current_admin.username:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot deactivate your own account"
        )
    
    user = user_db.update_user(username, {"is_active": is_active})
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    status_text = "activated" if is_active else "deactivated"
    return {"message": f"User {username} {status_text} successfully", "is_active": is_active}

@router.put("/admin/users/{username}")
async def update_user(
    username: str,
    user_update: UserUpdate,
    current_admin: UserResponse = Depends(get_current_admin_user)
):
    """Update user information (admin only)."""
    # Convert to dict and remove None values
    updates = {k: v for k, v in user_update.dict(exclude_unset=True).items() if v is not None}
    
    if not updates:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No fields to update"
        )
    
    # Prevent admin from deactivating themselves
    if username == current_admin.username and "is_active" in updates and not updates["is_active"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot deactivate your own account"
        )
    
    try:
        user = user_db.update_user(username, updates)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        return {"message": f"User {username} updated successfully"}
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"User update error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="User update failed"
        )
