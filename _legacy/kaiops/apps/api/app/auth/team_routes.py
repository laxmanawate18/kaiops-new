from fastapi import APIRouter, Depends, HTTPException, status
from typing import List, Dict, Any
from .models import (
    TeamCreate, TeamUpdate, TeamResponse, TeamMemberResponse,
    TeamAgentCreate, TeamAgentResponse,
    TeamAssignment, TeamAssignmentResponse, AgentType, AgentPriority,
    SystemStats, AgentStats
)
from .database_firestore import user_db
from .team_database_firestore import team_db
from .dependencies import get_current_user, get_current_admin_user
from .models import UserResponse, UserRole
import logging

logger = logging.getLogger(__name__)
router = APIRouter()

# Team Management Routes
@router.post("", response_model=TeamResponse)
async def create_team(
    team_data: TeamCreate,
    current_user: UserResponse = Depends(get_current_admin_user)
):
    """Create a new team (admin only)."""
    try:
        team = team_db.create_team(
            name=team_data.name,
            description=team_data.description
        )
        
        # Get member count (will be 0 for new team)
        members = team_db.get_team_members(team["id"])
        team_lead = None
        
        for member in members:
            if member["is_team_lead"]:
                user = user_db.get_user_by_id(member["user_id"])
                if user:
                    team_lead = {"id": user["id"], "username": user["username"]}
                break
        
        return TeamResponse(
            id=team["id"],
            name=team["name"],
            description=team["description"],
            is_active=team["is_active"],
            created_at=team["created_at"],
            updated_at=team["updated_at"],
            member_count=len(members),
            team_lead_id=team_lead["id"] if team_lead else None,
            team_lead_username=team_lead["username"] if team_lead else None
        )
        
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )

@router.get("", response_model=List[TeamResponse])
async def get_all_teams(
    current_user: UserResponse = Depends(get_current_user)
):
    """Get all teams."""
    teams = team_db.get_all_teams()
    team_responses = []
    
    for team in teams:
        members = team_db.get_team_members(team["id"])
        team_lead = None
        
        # Find team lead
        for member in members:
            if member["is_team_lead"]:
                user = user_db.get_user_by_id(member["user_id"])
                if user:
                    team_lead = {"id": user["id"], "username": user["username"]}
                break

        team_responses.append(TeamResponse(
            id=team["id"],
            name=team["name"],
            description=team["description"],
            is_active=team["is_active"],
            created_at=team["created_at"],
            updated_at=team["updated_at"],
            member_count=len(members),
            team_lead_id=team_lead["id"] if team_lead else None,
            team_lead_username=team_lead["username"] if team_lead else None
        ))
    
    return team_responses

# NOTE: /stats MUST be registered BEFORE /{team_id} so FastAPI matches the
# literal "stats" path instead of treating it as a team_id (BUG-P4-3 fix).
@router.get("/stats", response_model=SystemStats)
async def get_system_stats(
    current_user: UserResponse = Depends(get_current_admin_user)
):
    """Get system statistics (admin only)."""
    try:
        all_users = user_db.get_all_users()
        all_teams = team_db.get_all_teams()
        
        # Calculate agent statistics
        agent_stats_dict = {}
        for agent_type in AgentType:
            agent_stats_dict[agent_type.value] = {
                "total_teams": 0,
                "primary_teams": 0,
                "secondary_teams": 0
            }
        
        # Count team agent assignments
        total_agent_assignments = 0
        for team in all_teams:
            team_agents = team_db.get_team_agents(team["id"])
            total_agent_assignments += len(team_agents)
            
            for agent in team_agents:
                agent_type = agent["agent_type"]
                priority = agent["priority"]
                
                if agent_type in agent_stats_dict:
                    agent_stats_dict[agent_type]["total_teams"] += 1
                    if priority == "primary":
                        agent_stats_dict[agent_type]["primary_teams"] += 1
                    elif priority == "secondary":
                        agent_stats_dict[agent_type]["secondary_teams"] += 1
        
        # Create agent stats list
        agent_stats_list = []
        for agent_type, stats in agent_stats_dict.items():
            agent_stats_list.append(AgentStats(
                agent_type=AgentType(agent_type),
                total_teams=stats["total_teams"],
                primary_teams=stats["primary_teams"],
                secondary_teams=stats["secondary_teams"]
            ))
        
        return SystemStats(
            total_users=len(all_users),
            total_teams=len(all_teams),
            total_agent_assignments=total_agent_assignments,
            active_users=len([u for u in all_users if u.get("is_active", True)]),
            agents=agent_stats_list
        )
        
    except Exception as e:
        logger.error(f"Error getting system stats: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get system statistics"
        )

@router.get("/{team_id}", response_model=TeamResponse)
async def get_team(
    team_id: str,
    current_user: UserResponse = Depends(get_current_user)
):
    """Get a specific team."""
    team = team_db.get_team(team_id)
    if not team:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Team not found"
        )
    
    members = team_db.get_team_members(team_id)
    team_lead = None
    
    # Find team lead
    for member in members:
        if member["is_team_lead"]:
            user = user_db.get_user_by_id(member["user_id"])
            if user:
                team_lead = {"id": user["id"], "username": user["username"]}
            break

    return TeamResponse(
        id=team["id"],
        name=team["name"],
        description=team["description"],
        is_active=team["is_active"],
        created_at=team["created_at"],
        updated_at=team["updated_at"],
        member_count=len(members),
        team_lead_id=team_lead["id"] if team_lead else None,
        team_lead_username=team_lead["username"] if team_lead else None
    )

@router.put("/{team_id}", response_model=TeamResponse)
async def update_team(
    team_id: str,
    team_updates: TeamUpdate,
    current_user: UserResponse = Depends(get_current_admin_user)
):
    """Update a team (admin only)."""
    try:
        updates = {}
        if team_updates.name is not None:
            updates["name"] = team_updates.name
        if team_updates.description is not None:
            updates["description"] = team_updates.description
        if team_updates.is_active is not None:
            updates["is_active"] = team_updates.is_active
        
        team = team_db.update_team(team_id, updates)
        if not team:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Team not found"
            )
        
        members = team_db.get_team_members(team_id)
        team_lead = None
        
        for member in members:
            if member["is_team_lead"]:
                user = user_db.get_user_by_id(member["user_id"])
                if user:
                    team_lead = {"id": user["id"], "username": user["username"]}
                break

        return TeamResponse(
            id=team["id"],
            name=team["name"],
            description=team["description"],
            is_active=team["is_active"],
            created_at=team["created_at"],
            updated_at=team["updated_at"],
            member_count=len(members),
            team_lead_id=team_lead["id"] if team_lead else None,
            team_lead_username=team_lead["username"] if team_lead else None
        )
        
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )

@router.delete("/{team_id}")
async def delete_team(
    team_id: str,
    current_user: UserResponse = Depends(get_current_admin_user)
):
    """Delete a team (admin only)."""
    if team_db.delete_team(team_id):
        return {"message": f"Team deleted successfully"}
    else:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Team not found"
        )

# Team Member Management Routes
@router.post("/{team_id}/members")
async def assign_user_to_team(
    team_id: str,
    assignment: TeamAssignment,
    current_user: UserResponse = Depends(get_current_admin_user)
):
    """Assign a user to a team (admin only)."""
    try:
        # Verify user exists (assignment.user_id is a user id, not a username)
        user = user_db.get_user_by_id(assignment.user_id)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        assignment_data = team_db.assign_user_to_team(
            user_id=assignment.user_id,
            team_id=team_id,
            is_team_lead=assignment.is_team_lead or False,
            assigned_by=current_user.id
        )
        
        team = team_db.get_team(team_id)
        
        return TeamAssignmentResponse(
            id=assignment_data["id"],
            user_id=assignment_data["user_id"],
            team_id=assignment_data["team_id"],
            username=user["username"],
            team_name=team["name"] if team else "Unknown",
            is_team_lead=assignment_data["is_team_lead"],
            assigned_at=assignment_data["assigned_at"],
            assigned_by=assignment_data["assigned_by"]
        )
        
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )

@router.get("/{team_id}/members", response_model=List[TeamMemberResponse])
async def get_team_members(
    team_id: str,
    current_user: UserResponse = Depends(get_current_user)
):
    """Get all members of a team."""
    team = team_db.get_team(team_id)
    if not team:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Team not found"
        )
    
    members = team_db.get_team_members(team_id)
    member_responses = []
    
    for member in members:
        user = user_db.get_user_by_id(member["user_id"])
        if user:
            member_responses.append(TeamMemberResponse(
                user_id=user["id"],
                username=user["username"],
                full_name=user.get("full_name"),
                role=UserRole(user["role"]),
                joined_at=member["assigned_at"],
                is_team_lead=member["is_team_lead"]
            ))
    
    return member_responses

@router.delete("/{team_id}/members/{user_id}")
async def remove_user_from_team(
    team_id: str,
    user_id: str,
    current_user: UserResponse = Depends(get_current_admin_user)
):
    """Remove a user from a team (admin only)."""
    if team_db.remove_user_from_team(user_id, team_id):
        return {"message": "User removed from team successfully"}
    else:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User assignment not found"
        )

@router.put("/{team_id}/members/{user_id}/lead")
async def update_team_lead(
    team_id: str,
    user_id: str,
    is_team_lead: bool,
    current_user: UserResponse = Depends(get_current_admin_user)
):
    """Update team lead status for a user (admin only)."""
    if team_db.update_team_lead(team_id, user_id, is_team_lead):
        action = "promoted to" if is_team_lead else "removed from"
        return {"message": f"User {action} team lead successfully"}
    else:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User assignment not found"
        )

# Agent Management Routes
@router.post("/{team_id}/agents", response_model=TeamAgentResponse)
async def assign_team_agent(
    team_id: str,
    agent: TeamAgentCreate,
    current_user: UserResponse = Depends(get_current_admin_user)
):
    """Assign an agent to a team with priority (admin only)."""
    try:
        agent_data = team_db.assign_team_agent(
            team_id=team_id,
            agent_type=agent.agent_type,
            priority=agent.priority,
            assigned_by=current_user.id
        )
        
        team = team_db.get_team(team_id)
        team_name = team["name"] if team else "Unknown"
        
        return TeamAgentResponse(
            id=agent_data["id"],
            team_id=agent_data["team_id"],
            team_name=team_name,
            agent_type=agent_data["agent_type"],
            priority=agent_data["priority"],
            assigned_by=agent_data["assigned_by"],
            assigned_at=agent_data["assigned_at"]
        )
        
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Error assigning team agent: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to assign agent"
        )

@router.get("/{team_id}/agents", response_model=List[TeamAgentResponse])
async def get_team_agents(
    team_id: str,
    priority: str = None,
    current_user: UserResponse = Depends(get_current_user)
):
    """Get all agent assignments for a team, optionally filtered by priority."""
    agents = team_db.get_team_agents(team_id, priority)
    agent_responses = []
    
    team = team_db.get_team(team_id)
    team_name = team["name"] if team else "Unknown"
    
    for agent in agents:
        agent_responses.append(TeamAgentResponse(
            id=agent["id"],
            team_id=agent["team_id"],
            team_name=team_name,
            agent_type=agent["agent_type"],
            priority=agent["priority"],
            assigned_by=agent["assigned_by"],
            assigned_at=agent["assigned_at"]
        ))
    
    return agent_responses

@router.delete("/{team_id}/agents/{agent_id}")
async def remove_team_agent(
    team_id: str,
    agent_id: str,
    current_user: UserResponse = Depends(get_current_admin_user)
):
    """Remove an agent assignment from a team (admin only)."""
    if team_db.remove_team_agent(agent_id):
        return {"message": "Agent removed successfully"}
    else:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Agent assignment not found"
        )

@router.get("/agents/types", response_model=List[str])
async def get_available_agent_types(
    current_user: UserResponse = Depends(get_current_user)
):
    """Get list of available agent types."""
    return [agent.value for agent in AgentType]

@router.get("/agents/priorities", response_model=List[str])
async def get_agent_priorities(
    current_user: UserResponse = Depends(get_current_user)
):
    """Get list of available agent priorities."""
    return [priority.value for priority in AgentPriority]
