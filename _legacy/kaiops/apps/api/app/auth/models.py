from pydantic import BaseModel, EmailStr, validator, Field
from typing import Optional, List, Dict, Any
from enum import Enum
import re

class UserRole(str, Enum):
    USER = "user"
    ADMIN = "admin"
    TEAM_LEAD = "team_lead"

class AgentType(str, Enum):
    """SRE Agent Types"""
    COST_AGENT = "cost_agent"
    METADATA_AGENT = "metadata_agent"
    CUSTOM_AGENT = "custom_agent"

class AgentPriority(str, Enum):
    """Agent priority level for teams"""
    PRIMARY = "primary"
    SECONDARY = "secondary"

# Team Models
class TeamCreate(BaseModel):
    name: str = Field(..., min_length=2, max_length=100)
    description: Optional[str] = Field(None, max_length=500)
    
    @validator('name')
    def validate_team_name(cls, v):
        if not re.match(r'^[a-zA-Z0-9\s_-]+$', v):
            raise ValueError('Team name can only contain letters, numbers, spaces, hyphens, and underscores')
        return v.strip()

class TeamUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=2, max_length=100)
    description: Optional[str] = Field(None, max_length=500)
    is_active: Optional[bool] = None

class TeamResponse(BaseModel):
    id: str
    name: str
    description: Optional[str] = None
    is_active: bool
    created_at: str
    updated_at: Optional[str] = None  # Absent on teams seeded before updated_at was written
    member_count: int
    team_lead_id: Optional[str] = None
    team_lead_username: Optional[str] = None

class TeamMemberResponse(BaseModel):
    user_id: str
    username: str
    full_name: Optional[str] = None
    role: UserRole
    joined_at: str
    is_team_lead: bool

# Agent Assignment Models
class TeamAgentCreate(BaseModel):
    """Model for assigning an agent to a team"""
    team_id: str
    agent_type: AgentType
    priority: AgentPriority
    
class TeamAgentResponse(BaseModel):
    """Response model for team agent assignments"""
    id: str
    team_id: str
    team_name: str
    agent_type: AgentType
    priority: AgentPriority
    assigned_by: str
    assigned_at: str

# Team Assignment Models
class TeamAssignment(BaseModel):
    user_id: str
    team_id: str
    is_team_lead: Optional[bool] = False

class TeamAssignmentResponse(BaseModel):
    id: str
    user_id: str
    team_id: str
    username: str
    team_name: str
    is_team_lead: bool
    assigned_at: str
    assigned_by: str

# Updated User Models
class UserCreate(BaseModel):
    username: str = Field(..., min_length=3, max_length=50)
    email: EmailStr
    password: str = Field(..., min_length=10, max_length=128)
    full_name: Optional[str] = Field(None, max_length=100)
    role: Optional[UserRole] = UserRole.USER
    
    @validator('username')
    def validate_username(cls, v):
        if not re.match(r'^[a-zA-Z0-9_-]+$', v):
            raise ValueError('Username can only contain letters, numbers, hyphens, and underscores')
        return v
    
    @validator('password')
    def validate_password(cls, v):
        if len(v) < 10:
            raise ValueError('Password must be at least 10 characters long')
        if len(v) > 128:
            raise ValueError('Password cannot be longer than 128 characters')
        if not re.search(r'[A-Za-z]', v):
            raise ValueError('Password must contain at least one letter')
        if not re.search(r'[0-9]', v):
            raise ValueError('Password must contain at least one number')
        if not re.search(r'[A-Z]', v):
            raise ValueError('Password must contain at least one uppercase letter')
        return v

class UserUpdate(BaseModel):
    full_name: Optional[str] = Field(None, max_length=100)
    role: Optional[UserRole] = None
    is_active: Optional[bool] = None

class UserResponse(BaseModel):
    id: str
    username: str
    email: str
    full_name: Optional[str] = None
    role: UserRole
    is_active: bool
    created_at: str
    teams: List[str] = []  # Team names
    team_lead_of: List[str] = []  # Teams where user is team lead

class UserLogin(BaseModel):
    username: str = Field(..., min_length=1, max_length=50)
    password: str = Field(..., min_length=1, max_length=128)

class Token(BaseModel):
    access_token: str
    token_type: str
    expires_in: int
    user: UserResponse
    refresh_token: Optional[str] = None

class RefreshTokenRequest(BaseModel):
    refresh_token: str

class TokenData(BaseModel):
    username: Optional[str] = None
    role: Optional[UserRole] = None

class PasswordChange(BaseModel):
    current_password: str = Field(..., min_length=1, max_length=128)
    new_password: str = Field(..., min_length=10, max_length=128)
    
    @validator('new_password')
    def validate_new_password(cls, v):
        if len(v) < 10:
            raise ValueError('New password must be at least 10 characters long')
        if len(v) > 128:
            raise ValueError('New password cannot be longer than 128 characters')
        if not re.search(r'[A-Za-z]', v):
            raise ValueError('New password must contain at least one letter')
        if not re.search(r'[0-9]', v):
            raise ValueError('New password must contain at least one number')
        if not re.search(r'[A-Z]', v):
            raise ValueError('New password must contain at least one uppercase letter')
        return v

# Dashboard Models
class AgentStats(BaseModel):
    """Stats for a specific agent"""
    agent_type: AgentType
    total_teams: int
    primary_teams: int
    secondary_teams: int

class SystemStats(BaseModel):
    """Overall system statistics"""
    total_users: int
    total_teams: int
    total_agent_assignments: int
    active_users: int
    agents: List[AgentStats]
