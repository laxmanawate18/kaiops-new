from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from typing import Optional
from .utils import verify_token
from .database_firestore import user_db
from .team_database_firestore import team_db
from .models import UserRole, UserResponse, AgentType, AgentPriority

security = HTTPBearer()

async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)) -> UserResponse:
    """Get current authenticated user."""
    token_data = verify_token(credentials.credentials)
    username = token_data["username"]
    
    user = user_db.get_user(username)
    if user is None:
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
    
    # Get user's teams
    user_teams = team_db.get_user_teams(user["id"])
    teams = [team["name"] for team in user_teams]
    team_lead_of = [team["name"] for team in user_teams if team.get("is_team_lead", False)]
    
    return UserResponse(
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

async def get_current_admin_user(current_user: UserResponse = Depends(get_current_user)) -> UserResponse:
    """Get current user if they are an admin."""
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions"
        )
    return current_user

async def get_current_admin_or_team_lead(current_user: UserResponse = Depends(get_current_user)) -> UserResponse:
    """Get current user if they are an admin or team lead."""
    if current_user.role not in [UserRole.ADMIN, UserRole.TEAM_LEAD]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin or Team Lead access required"
        )
    return current_user

_optional_security = HTTPBearer(auto_error=False)

async def get_optional_current_user(credentials: Optional[HTTPAuthorizationCredentials] = Depends(_optional_security)) -> Optional[UserResponse]:
    """Get current user if authenticated, None otherwise."""
    if not credentials:
        return None

    try:
        return await get_current_user(credentials)
    except HTTPException:
        return None

def require_agent_access(agent_type: AgentType, priority: AgentPriority = None):
    """Dependency to check if user's team has access to a specific agent."""
    def agent_checker(current_user: UserResponse = Depends(get_current_user)) -> UserResponse:
        if current_user.role == UserRole.ADMIN:
            return current_user

        # Check if any of the user's teams have the requested agent assigned.
        # Assignments live in the "team_agents" collection, not on the team doc.
        required_priority = priority.value if priority is not None else None

        teams = team_db.get_user_teams(current_user.id)
        for team in teams:
            for assignment in team_db.get_team_agents(team["id"]):
                if assignment.get("agent_type") != agent_type.value:
                    continue
                if required_priority and assignment.get("priority") != required_priority:
                    continue
                return current_user

        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Your team does not have access to agent: {agent_type.value}"
        )

    return agent_checker
