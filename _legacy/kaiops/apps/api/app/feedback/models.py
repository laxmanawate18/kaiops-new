from pydantic import BaseModel, Field
from typing import Optional, List
from enum import Enum

class FeedbackType(str, Enum):
    THUMBS_UP = "THUMBS_UP"
    THUMBS_DOWN = "THUMBS_DOWN"
    COPY = "COPY"
    REWRITE = "REWRITE"
    FEATURE_REQUEST = "FEATURE_REQUEST"

class FeedbackStatus(str, Enum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    DENIED = "DENIED"
    RECLASSIFIED = "RECLASSIFIED"

class FeedbackCategory(str, Enum):
    ACCURACY = "accuracy"
    RELEVANCE = "relevance"
    HELPFULNESS = "helpfulness"
    TONE = "tone"
    COMPLETENESS = "completeness"
    SAFETY = "safety"
    OTHER = "other"

class DatasetType(str, Enum):
    TRAINING = "training"
    EVALUATION = "evaluation"
    BOTH = "both"

# Request Models
class FeedbackCreate(BaseModel):
    conversation_id: str = Field(..., description="ID of the conversation")
    message_id: str = Field(..., description="ID of the specific message")
    user_message: str = Field(..., description="Original user message")
    ai_response: str = Field(..., description="AI response being rated")
    feedback_type: FeedbackType
    rating: Optional[int] = Field(None, ge=1, le=5, description="Rating 1-5 for thumbs up")
    tags: Optional[List[FeedbackCategory]] = Field(default_factory=list)
    # Validated single primary category (was previously silently dropped when
    # clients sent it; unknown values now 422 instead of vanishing).
    category: Optional[FeedbackCategory] = None
    comment: Optional[str] = Field(None, max_length=1000)
    suggested_response: Optional[str] = Field(None, max_length=2000, description="User's suggested better response")

class FeedbackUpdate(BaseModel):
    comment: Optional[str] = Field(None, max_length=1000)
    tags: Optional[List[FeedbackCategory]] = None
    suggested_response: Optional[str] = Field(None, max_length=2000)

class FeedbackReview(BaseModel):
    status: FeedbackStatus
    reviewer_comment: Optional[str] = Field(None, max_length=1000)
    new_tags: Optional[List[FeedbackCategory]] = None
    add_to_dataset: Optional[DatasetType] = None

# Response Models
class FeedbackResponse(BaseModel):
    id: str
    conversation_id: Optional[str] = None  # Optional for backward compatibility
    message_id: Optional[str] = None  # Optional for backward compatibility
    user_id: str
    username: str
    user_message: Optional[str] = None  # Optional for backward compatibility
    ai_response: Optional[str] = None  # Optional for backward compatibility
    feedback_type: FeedbackType
    rating: Optional[int] = None
    tags: List[FeedbackCategory] = Field(default_factory=list)
    comment: Optional[str] = None
    suggested_response: Optional[str] = None
    status: FeedbackStatus
    reviewer_id: Optional[str] = None
    reviewer_username: Optional[str] = None
    reviewer_comment: Optional[str] = None
    dataset_type: Optional[DatasetType] = None
    created_at: str
    updated_at: str
    reviewed_at: Optional[str] = None

class FeedbackStats(BaseModel):
    total_feedback: int
    pending_review: int
    approved: int
    denied: int
    reclassified: int
    thumbs_up_count: int
    thumbs_down_count: int
    avg_rating: Optional[float] = None
    feedback_by_category: dict
    feedback_by_user: dict

class DatasetEntry(BaseModel):
    id: str
    feedback_id: str
    user_message: str
    ai_response: str
    expected_response: Optional[str] = None
    tags: List[FeedbackCategory]
    dataset_type: DatasetType
    quality_score: Optional[float] = None
    created_at: str
    created_by: str

class DatasetStats(BaseModel):
    training_count: int
    evaluation_count: int
    total_entries: int
    categories_breakdown: dict
    quality_distribution: dict
