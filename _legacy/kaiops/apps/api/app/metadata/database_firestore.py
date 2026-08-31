"""
Metadata Database with Firestore

Firestore operations for application metadata storage and retrieval.
"""
import logging
from typing import Optional, List, Dict, Any
from datetime import datetime
from google.cloud.firestore_v1.base_query import FieldFilter

from ..database.firestore_config import FirestoreConfig

import uuid

logger = logging.getLogger(__name__)


class MetadataDatabase:
    """Firestore database operations for application metadata."""
    
    def __init__(self):
        """Initialize metadata database."""
        try:
            self.client = FirestoreConfig.get_client()
            self.collection = self.client.collection("application_metadata")
            logger.info("[OK] Metadata database initialized with Firestore")
        except Exception as e:
            logger.error(f"Failed to initialize metadata database: {e}")
            raise
    
    # ==================== CREATE OPERATIONS ====================
    
    def create_metadata(self, app_name: str, application_id: str, team: str, **kwargs) -> Dict[str, Any]:
        """Create metadata for an application."""
        try:
            doc_id = str(uuid.uuid4())
            
            metadata = {
                "id": doc_id,
                "application_id": application_id,
                "app_name": app_name,
                "team": team,
                "environment": kwargs.get("environment"),
                "metadata_json": kwargs.get("metadata_json", {}),
                "created_at": datetime.now().isoformat(),
                "updated_at": None
            }
            
            self.collection.document(doc_id).set(metadata)
            
            logger.info(f"[OK] Created metadata for app: {app_name}")
            return metadata
            
        except Exception as e:
            logger.error(f"[FAIL] Error creating metadata: {e}")
            raise
    
    # ==================== READ OPERATIONS ====================
    
    def get_metadata(self, app_name: str) -> Optional[Dict[str, Any]]:
        """Get metadata for an application by name."""
        try:
            # Firestore doesn't do case-insensitive search easily, using exact match
            docs = self.collection.where(filter=FieldFilter("app_name", "==", app_name)).limit(1).get()
            for doc in docs:
                return doc.to_dict()
                
            # Fallback for case-insensitive
            all_docs = self.collection.stream()
            for doc in all_docs:
                data = doc.to_dict()
                if data.get("app_name", "").lower() == app_name.lower():
                    return data
            return None
            
        except Exception as e:
            logger.error(f"Error getting metadata for {app_name}: {e}")
            return None
    
    def get_by_team(self, team: str) -> List[Dict[str, Any]]:
        """Retrieve all metadata for a specific team."""
        try:
            docs = self.collection.where(filter=FieldFilter("team", "==", team)).stream()
            
            result = [doc.to_dict() for doc in docs]
            result.sort(key=lambda x: x.get("app_name", ""))
            
            logger.info(f"Retrieved {len(result)} metadata records for team: {team}")
            return result
            
        except Exception as e:
            logger.error(f"Error retrieving metadata for team {team}: {e}")
            return []
    
    def get_all_metadata(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Get all application metadata."""
        try:
            docs = list(self.collection.stream())
            result = [doc.to_dict() for doc in docs]
            result.sort(key=lambda x: x.get("created_at", ""), reverse=True)
            return result[:limit]
            
        except Exception as e:
            logger.error(f"Error getting all metadata: {e}")
            return []
    
    def get_by_environment(self, environment: str) -> List[Dict[str, Any]]:
        """Get metadata filtered by environment (dev, staging, prod)."""
        try:
            docs = self.collection.where(filter=FieldFilter("environment", "==", environment)).stream()
            return [doc.to_dict() for doc in docs]
            
        except Exception as e:
            logger.error(f"Error getting metadata by environment {environment}: {e}")
            return []
    
    # ==================== UPDATE OPERATIONS ====================
    
    def update_metadata(self, app_name: str, updates: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Update metadata for an application."""
        try:
            # Find the document ID first
            doc_id = None
            docs = self.collection.where(filter=FieldFilter("app_name", "==", app_name)).limit(1).get()
            for doc in docs:
                doc_id = doc.id
                
            if not doc_id:
                # Fallback to case insensitive
                all_docs = self.collection.stream()
                for doc in all_docs:
                    if doc.to_dict().get("app_name", "").lower() == app_name.lower():
                        doc_id = doc.id
                        break
                        
            if not doc_id:
                logger.warning(f"Metadata for {app_name} not found")
                return None
            
            doc_ref = self.collection.document(doc_id)
            
            # Update allowed fields
            allowed_fields = ['team', 'environment', 'metadata_json']
            filtered_updates = {k: v for k, v in updates.items() if k in allowed_fields}
            
            if filtered_updates:
                filtered_updates['updated_at'] = datetime.now().isoformat()
                doc_ref.update(filtered_updates)
            
            result = doc_ref.get().to_dict()
            
            logger.info(f"[OK] Updated metadata for: {app_name}")
            return result
            
        except Exception as e:
            logger.error(f"[FAIL] Error updating metadata: {e}")
            raise
    
    # ==================== DELETE OPERATIONS ====================
    
    def delete_metadata(self, app_name: str) -> bool:
        """Delete metadata for an application."""
        try:
            doc_id = None
            docs = self.collection.where(filter=FieldFilter("app_name", "==", app_name)).limit(1).get()
            for doc in docs:
                doc_id = doc.id
                
            if not doc_id:
                all_docs = self.collection.stream()
                for doc in all_docs:
                    if doc.to_dict().get("app_name", "").lower() == app_name.lower():
                        doc_id = doc.id
                        break
                        
            if not doc_id:
                logger.warning(f"Metadata for {app_name} not found")
                return False
            
            self.collection.document(doc_id).delete()
            
            logger.info(f"[OK] Deleted metadata for: {app_name}")
            return True
            
        except Exception as e:
            logger.error(f"[FAIL] Error deleting metadata: {e}")
            return False
    
    # ==================== SEARCH & FILTERING ====================
    
    def search_metadata(self, search_term: str) -> List[Dict[str, Any]]:
        """Search metadata by application name or team."""
        try:
            search_term = search_term.lower()
            all_docs = self.collection.stream()
            results = []
            
            for doc in all_docs:
                data = doc.to_dict()
                name = data.get("app_name", "").lower()
                team = data.get("team", "").lower()
                
                if search_term in name or search_term in team:
                    results.append(data)
            
            return results
            
        except Exception as e:
            logger.error(f"Error searching metadata: {e}")
            return []


# Global metadata database instance
metadata_db = MetadataDatabase()
