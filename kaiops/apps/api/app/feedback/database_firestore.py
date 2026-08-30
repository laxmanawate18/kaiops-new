"""
Feedback Database with Firestore

Persistent storage for AI feedback and training datasets.
"""
from typing import Dict, Optional, List
from datetime import datetime
from google.cloud.firestore_v1.base_query import FieldFilter
from ..database.firestore_config import FirestoreConfig
from .models import FeedbackStatus, FeedbackType, DatasetType
import uuid
import logging

logger = logging.getLogger(__name__)


class FeedbackDatabase:
    """Firestore-backed feedback database for AI response improvement."""
    
    def __init__(self):
        """Initialize feedback database."""
        try:
            self.client = FirestoreConfig.get_client()
            self.feedback_collection = self.client.collection("feedback")
            self.training_collection = self.client.collection("training_datasets")
            self.evaluation_collection = self.client.collection("evaluation_datasets")
            logger.info("[OK] Feedback database initialized with Firestore")
        except Exception as e:
            logger.error(f"Failed to initialize feedback database: {e}")
            raise
    
    # ==================== NORMALISATION HELPERS ====================

    @staticmethod
    def _enum_value(value, default: Optional[str] = None) -> Optional[str]:
        """Coerce an enum / string status or type into its canonical UPPERCASE value."""
        if value is None:
            return default
        if hasattr(value, "value"):
            value = value.value
        return str(value).upper()

    @classmethod
    def _normalize_doc(cls, data: Optional[Dict]) -> Optional[Dict]:
        """Upper-case legacy lowercase status/feedback_type values written by older code."""
        if not data:
            return data
        for field in ("status", "feedback_type"):
            raw = data.get(field)
            if isinstance(raw, str) and raw != raw.upper():
                data[field] = raw.upper()
        return data

    # ==================== FEEDBACK MANAGEMENT ====================

    def create_feedback(self, user_id: str, feedback_data: Dict) -> Dict:
        """Create new feedback entry."""
        try:
            doc_id = str(uuid.uuid4())
            
            # Store detailed feedback info in metadata
            metadata = {
                "conversation_id": feedback_data.get("conversation_id"),
                "message_id": feedback_data.get("message_id"),
                "user_message": feedback_data.get("user_message"),
                "ai_response": feedback_data.get("ai_response"),
                "tags": feedback_data.get("tags", []),
                "suggested_response": feedback_data.get("suggested_response"),
            }
            
            feedback = {
                "id": doc_id,
                "user_id": user_id,
                "feedback_type": self._enum_value(feedback_data.get("feedback_type")),
                "status": FeedbackStatus.PENDING.value,
                "content": feedback_data.get("comment", ""),
                "rating": feedback_data.get("rating"),
                "related_response_id": feedback_data.get("message_id"),
                "created_at": datetime.now().isoformat(),
                "updated_at": datetime.now().isoformat(),
                "metadata_json": metadata,
                
                # Extract fields from metadata for API response (with defaults for backward compatibility)
                "conversation_id": metadata.get("conversation_id") or "legacy",
                "message_id": metadata.get("message_id") or doc_id,
                "user_message": metadata.get("user_message") or feedback_data.get("comment", ""),
                "ai_response": metadata.get("ai_response") or "N/A",
                "tags": metadata.get("tags") or [],
                "comment": feedback_data.get("comment", ""),
                "suggested_response": metadata.get("suggested_response"),
                "metadata": metadata
            }
            
            self.feedback_collection.document(doc_id).set(feedback)
            
            logger.info(f"[OK] Created feedback: {doc_id}")
            return feedback
            
        except Exception as e:
            logger.error(f"[FAIL] Error creating feedback: {e}")
            raise
    
    def get_feedback(self, feedback_id: str) -> Optional[Dict]:
        """Get feedback by ID."""
        try:
            doc = self.feedback_collection.document(feedback_id).get()
            if doc.exists:
                return self._normalize_doc(doc.to_dict())
            return None
        except Exception as e:
            logger.error(f"Error getting feedback {feedback_id}: {e}")
            return None

    def get_user_feedback(self, user_id: str, limit: int = 50) -> List[Dict]:
        """Get feedback by user."""
        try:
            docs = self.feedback_collection.where(filter=FieldFilter("user_id", "==", user_id)).stream()
            result = [self._normalize_doc(doc.to_dict()) for doc in docs]
            result.sort(key=lambda x: x.get("created_at", ""), reverse=True)
            return result[:limit]
        except Exception as e:
            logger.error(f"Error getting feedback for user {user_id}: {e}")
            return []

    def get_pending_feedback(self, limit: int = 100) -> List[Dict]:
        """Get all pending feedback for review."""
        try:
            # Match both the canonical value and the legacy lowercase one written by old code
            pending = FeedbackStatus.PENDING.value
            docs = self.feedback_collection.where(
                filter=FieldFilter("status", "in", [pending, pending.lower()])
            ).stream()
            result = [self._normalize_doc(doc.to_dict()) for doc in docs]
            result.sort(key=lambda x: x.get("created_at", ""))
            return result[:limit]
        except Exception as e:
            logger.error(f"Error getting pending feedback: {e}")
            return []

    def get_feedback_by_status(self, status: str, limit: int = 100) -> List[Dict]:
        """Get feedback by status."""
        try:
            status_value = self._enum_value(status)
            docs = self.feedback_collection.where(
                filter=FieldFilter("status", "in", [status_value, status_value.lower()])
            ).stream()
            result = [self._normalize_doc(doc.to_dict()) for doc in docs]
            result.sort(key=lambda x: x.get("updated_at", ""), reverse=True)
            return result[:limit]
        except Exception as e:
            logger.error(f"Error getting feedback by status {status}: {e}")
            return []
    
    def update_feedback_status(self, feedback_id: str, status: str) -> Optional[Dict]:
        """Update feedback status."""
        try:
            doc_ref = self.feedback_collection.document(feedback_id)
            if not doc_ref.get().exists:
                logger.warning(f"Feedback {feedback_id} not found")
                return None
            
            updates = {
                "status": self._enum_value(status, FeedbackStatus.PENDING.value),
                "updated_at": datetime.now().isoformat()
            }
            doc_ref.update(updates)

            logger.info(f"[OK] Updated feedback status: {feedback_id}")
            return self._normalize_doc(doc_ref.get().to_dict())
            
        except Exception as e:
            logger.error(f"[FAIL] Error updating feedback: {e}")
            raise
    
    def review_feedback(self, feedback_id: str, reviewer_id: str, review_data: Dict) -> Optional[Dict]:
        """Review feedback and update status."""
        try:
            doc_ref = self.feedback_collection.document(feedback_id)
            doc = doc_ref.get()
            if not doc.exists:
                logger.warning(f"Feedback {feedback_id} not found")
                return None
            
            current_data = self._normalize_doc(doc.to_dict())

            updates = {
                "status": self._enum_value(
                    review_data.get("status") or current_data.get("status"),
                    FeedbackStatus.PENDING.value
                ),
                "reviewer_id": reviewer_id,
                "reviewer_comment": review_data.get("reviewer_comment"),
                "reviewed_at": datetime.now().isoformat(),
                "updated_at": datetime.now().isoformat()
            }
            
            # Update tags if provided
            if review_data.get("new_tags"):
                updates["tags"] = review_data.get("new_tags")
                
                # Also update metadata tags
                metadata = current_data.get("metadata_json", {})
                metadata["tags"] = review_data.get("new_tags")
                updates["metadata_json"] = metadata
                updates["metadata"] = metadata
            
            doc_ref.update(updates)

            logger.info(f"[OK] Reviewed feedback: {feedback_id}")
            return self._normalize_doc(doc_ref.get().to_dict())
            
        except Exception as e:
            logger.error(f"[FAIL] Error reviewing feedback: {e}")
            raise
    
    def get_feedback_stats(self) -> Dict:
        """Get feedback statistics."""
        try:
            all_docs = list(self.feedback_collection.stream())
            
            total = len(all_docs)
            pending = 0
            approved = 0
            denied = 0
            reclassified = 0
            
            thumbs_up = 0
            thumbs_down = 0
            
            total_rating = 0
            rated_count = 0
            
            feedback_by_category = {}
            feedback_by_user = {}
            
            for doc in all_docs:
                data = self._normalize_doc(doc.to_dict())

                status = data.get("status")
                if status == FeedbackStatus.PENDING.value: pending += 1
                elif status == FeedbackStatus.APPROVED.value: approved += 1
                elif status == FeedbackStatus.DENIED.value: denied += 1
                elif status == FeedbackStatus.RECLASSIFIED.value: reclassified += 1

                fb_type = data.get("feedback_type")
                if fb_type == FeedbackType.THUMBS_UP.value: thumbs_up += 1
                elif fb_type == FeedbackType.THUMBS_DOWN.value: thumbs_down += 1

                rating = data.get("rating")
                if rating is not None:
                    total_rating += rating
                    rated_count += 1
                    
                tags = data.get("tags", [])
                for tag in tags:
                    feedback_by_category[tag] = feedback_by_category.get(tag, 0) + 1
                    
                user_id = data.get("user_id")
                if user_id:
                    feedback_by_user[user_id] = feedback_by_user.get(user_id, 0) + 1
            
            avg_rating = total_rating / rated_count if rated_count > 0 else None
            
            return {
                "total_feedback": total,
                "pending_review": pending,
                "approved": approved,
                "denied": denied,
                "reclassified": reclassified,
                "thumbs_up_count": thumbs_up,
                "thumbs_down_count": thumbs_down,
                "avg_rating": avg_rating,
                "feedback_by_category": feedback_by_category,
                "feedback_by_user": feedback_by_user
            }
            
        except Exception as e:
            logger.error(f"Error getting feedback stats: {e}")
            return {
                "total_feedback": 0,
                "pending_review": 0,
                "approved": 0,
                "denied": 0,
                "reclassified": 0,
                "thumbs_up_count": 0,
                "thumbs_down_count": 0,
                "avg_rating": None,
                "feedback_by_category": {},
                "feedback_by_user": {}
            }
    
    def get_user_feedback_stats(self, user_id: str) -> Dict:
        """Get feedback statistics for a specific user."""
        try:
            docs = self.feedback_collection.where(filter=FieldFilter("user_id", "==", user_id)).stream()
            
            total = 0
            pending = 0
            approved = 0
            denied = 0
            thumbs_up = 0
            thumbs_down = 0
            
            for doc in docs:
                data = self._normalize_doc(doc.to_dict())
                total += 1

                status = data.get("status")
                if status == FeedbackStatus.PENDING.value: pending += 1
                elif status == FeedbackStatus.APPROVED.value: approved += 1
                elif status == FeedbackStatus.DENIED.value: denied += 1

                fb_type = data.get("feedback_type")
                if fb_type == FeedbackType.THUMBS_UP.value: thumbs_up += 1
                elif fb_type == FeedbackType.THUMBS_DOWN.value: thumbs_down += 1


            return {
                "total_feedback": total,
                "pending": pending,
                "approved": approved,
                "denied": denied,
                "thumbs_up": thumbs_up,
                "thumbs_down": thumbs_down
            }
            
        except Exception as e:
            logger.error(f"Error getting user feedback stats: {e}")
            return {
                "total_feedback": 0,
                "pending": 0,
                "approved": 0,
                "denied": 0,
                "thumbs_up": 0,
                "thumbs_down": 0
            }
    
    # ==================== DATASET MANAGEMENT ====================
    
    def add_training_data(self, user_id: str, input_text: str, output_text: str, **kwargs) -> Dict:
        """Add training data entry."""
        try:
            doc_id = str(uuid.uuid4())
            
            training = {
                "id": doc_id,
                "user_id": user_id,
                "input_text": input_text,
                "output_text": output_text,
                "score": kwargs.get("score"),
                "category": kwargs.get("category"),
                "created_at": datetime.now().isoformat(),
                "dataset_type": DatasetType.TRAINING.value if hasattr(DatasetType, 'value') else "training",
                "metadata": kwargs.get("metadata", {}),
                "metadata_json": kwargs.get("metadata", {})
            }
            
            self.training_collection.document(doc_id).set(training)
            
            logger.info(f"[OK] Added training data: {doc_id}")
            return training
            
        except Exception as e:
            logger.error(f"[FAIL] Error adding training data: {e}")
            raise
    
    def add_evaluation_data(self, user_id: str, input_text: str, expected_output: str, **kwargs) -> Dict:
        """Add evaluation data entry."""
        try:
            doc_id = str(uuid.uuid4())
            
            evaluation = {
                "id": doc_id,
                "user_id": user_id,
                "input_text": input_text,
                "expected_output": expected_output,
                "actual_output": kwargs.get("actual_output"),
                "accuracy_score": kwargs.get("accuracy_score"),
                "category": kwargs.get("category"),
                "created_at": datetime.now().isoformat(),
                "dataset_type": DatasetType.EVALUATION.value if hasattr(DatasetType, 'value') else "evaluation",
                "metadata": kwargs.get("metadata", {}),
                "metadata_json": kwargs.get("metadata", {})
            }
            
            self.evaluation_collection.document(doc_id).set(evaluation)
            
            logger.info(f"[OK] Added evaluation data: {doc_id}")
            return evaluation
            
        except Exception as e:
            logger.error(f"[FAIL] Error adding evaluation data: {e}")
            raise
    
    def get_dataset_entries(self, dataset_type: Optional[str] = None, limit: int = 100) -> List[Dict]:
        """Get dataset entries."""
        try:
            entries = []
            
            is_training = dataset_type == DatasetType.TRAINING.value if hasattr(DatasetType, 'value') else dataset_type == "training"
            is_evaluation = dataset_type == DatasetType.EVALUATION.value if hasattr(DatasetType, 'value') else dataset_type == "evaluation"
            
            if is_training or not dataset_type:
                training_docs = list(self.training_collection.stream())
                entries.extend([doc.to_dict() for doc in training_docs])
            
            if is_evaluation or not dataset_type:
                eval_docs = list(self.evaluation_collection.stream())
                entries.extend([doc.to_dict() for doc in eval_docs])
            
            entries.sort(key=lambda x: x.get("created_at", ""), reverse=True)
            return entries[:limit]
            
        except Exception as e:
            logger.error(f"Error getting dataset entries: {e}")
            return []
    
    def get_dataset_stats(self) -> Dict:
        """Get dataset statistics."""
        try:
            training_docs = list(self.training_collection.stream())
            eval_docs = list(self.evaluation_collection.stream())
            
            training_count = len(training_docs)
            evaluation_count = len(eval_docs)
            
            return {
                "training_count": training_count,
                "evaluation_count": evaluation_count,
                "total_entries": training_count + evaluation_count,
                "categories_breakdown": {},
                "quality_distribution": {}
            }
            
        except Exception as e:
            logger.error(f"Error getting dataset stats: {e}")
            return {}


# Global feedback database instance
feedback_db = FeedbackDatabase()
