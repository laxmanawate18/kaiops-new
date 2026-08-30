"""
Chat Session Models

Pydantic models for chat sessions and messages.
"""
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum


class MessageSender(str, Enum):
    """Message sender types."""
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"


class ChatMessage(BaseModel):
    """Individual chat message model."""
    id: str
    session_id: str
    user_id: str
    sender: MessageSender
    text: str
    timestamp: str
    metadata: Optional[Dict[str, Any]] = None
    
    class Config:
        use_enum_values = True


class ChatSession(BaseModel):
    """Chat session model."""
    id: str
    user_id: str
    name: str
    created_at: str
    last_modified: str
    message_count: int = 0
    is_active: bool = True
    metadata: Optional[Dict[str, Any]] = None
    
    class Config:
        use_enum_values = True


class CreateSessionRequest(BaseModel):
    """Request to create a new session."""
    name: Optional[str] = None


class CreateSessionResponse(BaseModel):
    """Response when creating a session."""
    session: ChatSession
    message: str = "Session created successfully"


class SendMessageRequest(BaseModel):
    """Request to send a message."""
    session_id: str
    message: str
    metadata: Optional[Dict[str, Any]] = None


class SendMessageResponse(BaseModel):
    """Response when sending a message."""
    # Optional so the success=False error envelope can actually be returned
    user_message: Optional[ChatMessage] = None
    agent_message: Optional[ChatMessage] = None
    session_id: str
    success: bool = True
    error_message: Optional[str] = None


class GetMessagesResponse(BaseModel):
    """Response for getting messages."""
    session_id: str
    messages: List[ChatMessage]
    total: int


class GetSessionsResponse(BaseModel):
    """Response for getting sessions."""
    sessions: List[ChatSession]
    total: int


class UpdateSessionRequest(BaseModel):
    """Request to update session details."""
    name: Optional[str] = None
    is_active: Optional[bool] = None
    metadata: Optional[Dict[str, Any]] = None


class DeleteSessionResponse(BaseModel):
    """Response when deleting a session."""
    session_id: str
    message: str = "Session deleted successfully"


class ChatStatsResponse(BaseModel):
    """Chat statistics response."""
    user_id: str
    total_sessions: int
    active_sessions: int
    total_messages: int
    sessions_created_today: int
