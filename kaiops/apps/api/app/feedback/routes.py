from fastapi import APIRouter, Depends, HTTPException, status, Query
from typing import List, Optional
from ..auth.dependencies import get_current_user, get_current_admin_user, get_current_admin_or_team_lead
from ..auth.models import UserResponse
from ..auth.database_firestore import user_db
from .models import (
    FeedbackCreate, FeedbackUpdate, FeedbackReview, FeedbackResponse,
    FeedbackStats, DatasetEntry, DatasetStats, FeedbackType, FeedbackStatus,
    FeedbackCategory, DatasetType
)
from .database_firestore import feedback_db
import logging

logger = logging.getLogger(__name__)
router = APIRouter()

# FIXED: Create feedback endpoint — no trailing slash so /api/v1/feedback
# responds directly (consistent with the other routes: /my, /pending, /stats)
# instead of FastAPI's 307 redirect to /feedback/.
@router.post("", response_model=FeedbackResponse)
async def create_feedback(
    feedback_data: FeedbackCreate,
    current_user: UserResponse = Depends(get_current_user)
):
    """Create feedback for an AI response."""
    try:
        feedback_dict = feedback_data.model_dump()
        # Merge a provided `category` into tags so it is persisted even when
        # the client only sends the singular field.
        if feedback_data.category and not feedback_dict.get("tags"):
            feedback_dict["tags"] = [feedback_data.category.value]
        elif feedback_data.category:
            existing = list(feedback_dict.get("tags") or [])
            if isinstance(existing and existing[0], FeedbackCategory):
                pass  # already enum objects; serializer handles them downstream
            if feedback_data.category.value not in [getattr(t, "value", t) for t in existing]:
                feedback_dict["tags"] = existing + [feedback_data.category.value]
        feedback = feedback_db.create_feedback(current_user.id, feedback_dict)
        
        return FeedbackResponse(
            id=feedback["id"],
            conversation_id=feedback["conversation_id"],
            message_id=feedback["message_id"],
            user_id=feedback["user_id"],
            username=current_user.username,
            user_message=feedback["user_message"],
            ai_response=feedback["ai_response"],
            feedback_type=feedback["feedback_type"],
            rating=feedback.get("rating"),
            tags=feedback.get("tags", []),
            comment=feedback.get("comment"),
            suggested_response=feedback.get("suggested_response"),
            status=feedback["status"],
            reviewer_id=feedback.get("reviewer_id"),
            reviewer_username=None,
            reviewer_comment=feedback.get("reviewer_comment"),
            dataset_type=feedback.get("dataset_type"),
            created_at=feedback["created_at"],
            updated_at=feedback["updated_at"],
            reviewed_at=feedback.get("reviewed_at")
        )
        
    except Exception as e:
        logger.error(f"Error creating feedback: {e}")
        raise HTTPException(status_code=500, detail="Failed to create feedback")

@router.get("/my", response_model=List[FeedbackResponse])
async def get_my_feedback(
    limit: int = Query(50, ge=1, le=100),
    current_user: UserResponse = Depends(get_current_user)
):
    """Get current user's feedback."""
    try:
        feedback_list = feedback_db.get_user_feedback(current_user.id, limit)
        
        responses = []
        for feedback in feedback_list:
            reviewer_username = None
            if feedback.get("reviewer_id"):
                reviewer = user_db.get_user_by_id(feedback["reviewer_id"])
                reviewer_username = reviewer["username"] if reviewer else None
            
            responses.append(FeedbackResponse(
                id=feedback["id"],
                conversation_id=feedback["conversation_id"],
                message_id=feedback["message_id"],
                user_id=feedback["user_id"],
                username=current_user.username,
                user_message=feedback["user_message"],
                ai_response=feedback["ai_response"],
                feedback_type=feedback["feedback_type"],
                rating=feedback.get("rating"),
                tags=feedback.get("tags", []),
                comment=feedback.get("comment"),
                suggested_response=feedback.get("suggested_response"),
                status=feedback["status"],
                reviewer_id=feedback.get("reviewer_id"),
                reviewer_username=reviewer_username,
                reviewer_comment=feedback.get("reviewer_comment"),
                dataset_type=feedback.get("dataset_type"),
                created_at=feedback["created_at"],
                updated_at=feedback["updated_at"],
                reviewed_at=feedback.get("reviewed_at")
            ))
        
        return responses
        
    except Exception as e:
        logger.error(f"Error getting user feedback: {e}")
        raise HTTPException(status_code=500, detail="Failed to get feedback")

@router.get("/my/stats")
async def get_my_feedback_stats(
    current_user: UserResponse = Depends(get_current_user)
):
    """Get current user's feedback statistics."""
    try:
        stats = feedback_db.get_user_feedback_stats(current_user.id)
        return stats
    except Exception as e:
        logger.error(f"Error getting user feedback stats: {e}")
        raise HTTPException(status_code=500, detail="Failed to get feedback stats")

# ---- Aliases matching frontend contract (/feedback/mine*) ----

@router.get("/mine", response_model=List[FeedbackResponse])
async def get_my_feedback_alias(
    limit: int = Query(50, ge=1, le=100),
    current_user: UserResponse = Depends(get_current_user)
):
    """Alias of GET /my — frontend contract compatibility."""
    return await get_my_feedback(limit=limit, current_user=current_user)


@router.get("/mine/stats")
async def get_my_feedback_stats_alias(
    current_user: UserResponse = Depends(get_current_user)
):
    """Alias of GET /my/stats — frontend contract compatibility."""
    return await get_my_feedback_stats(current_user=current_user)

@router.get("/pending", response_model=List[FeedbackResponse])
async def get_pending_feedback(
    limit: int = Query(100, ge=1, le=200),
    current_user: UserResponse = Depends(get_current_admin_or_team_lead)
):
    """Get all pending feedback for review (admin/team lead only)."""
    try:
        feedback_list = feedback_db.get_pending_feedback(limit)
        
        responses = []
        for feedback in feedback_list:
            user = user_db.get_user_by_id(feedback["user_id"])
            
            responses.append(FeedbackResponse(
                id=feedback["id"],
                conversation_id=feedback["conversation_id"],
                message_id=feedback["message_id"],
                user_id=feedback["user_id"],
                username=user["username"] if user else "Unknown",
                user_message=feedback["user_message"],
                ai_response=feedback["ai_response"],
                feedback_type=feedback["feedback_type"],
                rating=feedback.get("rating"),
                tags=feedback.get("tags", []),
                comment=feedback.get("comment"),
                suggested_response=feedback.get("suggested_response"),
                status=feedback["status"],
                reviewer_id=feedback.get("reviewer_id"),
                reviewer_username=None,
                reviewer_comment=feedback.get("reviewer_comment"),
                dataset_type=feedback.get("dataset_type"),
                created_at=feedback["created_at"],
                updated_at=feedback["updated_at"],
                reviewed_at=feedback.get("reviewed_at")
            ))
        
        return responses
        
    except Exception as e:
        logger.error(f"Error getting pending feedback: {e}")
        raise HTTPException(status_code=500, detail="Failed to get pending feedback")

@router.get("/stats", response_model=FeedbackStats)
async def get_feedback_stats(
    current_user: UserResponse = Depends(get_current_admin_or_team_lead)
):
    """Get feedback statistics (admin/team lead only)."""
    try:
        stats = feedback_db.get_feedback_stats()

        return FeedbackStats(
            total_feedback=stats.get("total_feedback", 0),
            pending_review=stats.get("pending_review", 0),
            approved=stats.get("approved", 0),
            denied=stats.get("denied", 0),
            reclassified=stats.get("reclassified", 0),
            thumbs_up_count=stats.get("thumbs_up_count", 0),
            thumbs_down_count=stats.get("thumbs_down_count", 0),
            avg_rating=stats.get("avg_rating"),
            feedback_by_category=stats.get("feedback_by_category", {}),
            feedback_by_user=stats.get("feedback_by_user", {})
        )

    except Exception as e:
        logger.error(f"Error getting feedback stats: {e}")
        raise HTTPException(status_code=500, detail="Failed to get feedback stats")

@router.post("/{feedback_id}/review", response_model=FeedbackResponse)
async def review_feedback(
    feedback_id: str,
    review: FeedbackReview,
    current_user: UserResponse = Depends(get_current_admin_or_team_lead)
):
    """Review feedback (admin/team lead only)."""
    try:
        feedback = feedback_db.get_feedback(feedback_id)
        if not feedback:
            raise HTTPException(status_code=404, detail="Feedback not found")
        
        review_dict = review.model_dump()
        updated_feedback = feedback_db.review_feedback(feedback_id, current_user.id, review_dict)
        
        user = user_db.get_user_by_id(updated_feedback["user_id"])
        reviewer = user_db.get_user_by_id(updated_feedback["reviewer_id"])
        
        return FeedbackResponse(
            id=updated_feedback["id"],
            conversation_id=updated_feedback["conversation_id"],
            message_id=updated_feedback["message_id"],
            user_id=updated_feedback["user_id"],
            username=user["username"] if user else "Unknown",
            user_message=updated_feedback["user_message"],
            ai_response=updated_feedback["ai_response"],
            feedback_type=updated_feedback["feedback_type"],
            rating=updated_feedback.get("rating"),
            tags=updated_feedback.get("tags", []),
            comment=updated_feedback.get("comment"),
            suggested_response=updated_feedback.get("suggested_response"),
            status=updated_feedback["status"],
            reviewer_id=updated_feedback.get("reviewer_id"),
            reviewer_username=reviewer["username"] if reviewer else None,
            reviewer_comment=updated_feedback.get("reviewer_comment"),
            dataset_type=updated_feedback.get("dataset_type"),
            created_at=updated_feedback["created_at"],
            updated_at=updated_feedback["updated_at"],
            reviewed_at=updated_feedback.get("reviewed_at")
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error reviewing feedback: {e}")
        raise HTTPException(status_code=500, detail="Failed to review feedback")

# Dataset Management Routes
@router.get("/datasets/entries", response_model=List[DatasetEntry])
async def get_dataset_entries(
    dataset_type: Optional[DatasetType] = Query(None),
    limit: int = Query(100, ge=1, le=200),
    current_user: UserResponse = Depends(get_current_admin_user)
):
    """Get dataset entries (admin only)."""
    try:
        entries = feedback_db.get_dataset_entries(dataset_type, limit)
        
        responses = []
        for entry in entries:
            responses.append(DatasetEntry(
                id=entry["id"],
                feedback_id=entry["feedback_id"],
                user_message=entry["user_message"],
                ai_response=entry["ai_response"],
                expected_response=entry.get("expected_response"),
                tags=entry.get("tags", []),
                dataset_type=entry["dataset_type"],
                quality_score=entry.get("quality_score"),
                created_at=entry["created_at"],
                created_by=entry["created_by"]
            ))
        
        return responses
        
    except Exception as e:
        logger.error(f"Error getting dataset entries: {e}")
        raise HTTPException(status_code=500, detail="Failed to get dataset entries")

@router.get("/datasets/stats")
async def get_dataset_stats(
    current_user: UserResponse = Depends(get_current_admin_user)
):
    """Get dataset statistics (admin only)."""
    # TODO: categories_breakdown and quality_distribution have no data source yet -
    # feedback_db.get_dataset_stats() only counts training/evaluation entries and
    # returns those two as empty dicts until per-entry categories/scores are stored.
    try:
        stats = feedback_db.get_dataset_stats()

        return {
            "training_count": stats.get("training_count", 0),
            "evaluation_count": stats.get("evaluation_count", 0),
            "total_entries": stats.get("total_entries", 0),
            "categories_breakdown": stats.get("categories_breakdown", {}),
            "quality_distribution": stats.get("quality_distribution", {})
        }

    except Exception as e:
        logger.error(f"Error getting dataset stats: {e}")
        raise HTTPException(status_code=500, detail="Failed to get dataset stats")

# Utility Routes
@router.get("/categories", response_model=List[str])
async def get_feedback_categories(
    current_user: UserResponse = Depends(get_current_user)
):
    """Get available feedback categories."""
    return [category.value for category in FeedbackCategory]
