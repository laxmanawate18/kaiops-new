"""
Application Database with Firestore

Persistent storage for SRE-enabled application registrations.
"""
from typing import Dict, Optional, List, Tuple
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeout
from google.cloud.firestore_v1.base_query import FieldFilter, BaseCompositeFilter
from ..database.firestore_config import FirestoreConfig
from .models import ApplicationStatus, ApplicationStats
import uuid
import logging

logger = logging.getLogger(__name__)

class ApplicationDatabase:
    """Firestore-backed database for managing SRE-enabled applications."""
    
    def __init__(self):
        """Initialize application database."""
        try:
            self.client = FirestoreConfig.get_client()
            self.collection = self.client.collection("applications")
            logger.info("[OK] Application database initialized with Firestore")
            ex = ThreadPoolExecutor(max_workers=1)
            try:
                ex.submit(self._ensure_demo_applications).result(timeout=12)
            except FuturesTimeout:
                logger.warning("[WARN] Demo application seeding timed out — Firestore unreachable at startup")
            finally:
                ex.shutdown(wait=False)
        except Exception as e:
            logger.error(f"Failed to initialize application database: {e}")
    
    def _ensure_demo_applications(self):
        """Ensure demo applications exist in Firestore."""
        try:
            # Check if demo apps already exist (short timeout so a bad ADC doesn't hang startup)
            docs = list(self.collection.limit(1).stream(timeout=8))
            if len(docs) > 0:
                logger.info(f"[STATS] Found existing applications in Firestore")
                return
            
            logger.info("Creating demo applications in Firestore...")
            
            demo_apps = [
                {
                    "application_name": "Payment Gateway",
                    "github_repo": "myorg/payment-gateway",
                    "gcp_project_id": "prod-payment-gw-001",
                    "argocd_app_name": "payment-gateway-prod",
                    "grafana_dashboard": "Payment Gateway Dashboard",
                    "gke_cluster_name": "prod-cluster-us-central1",
                    "namespace": "payment-prod",
                    "application_owner": "admin",
                    "status": ApplicationStatus.ACTIVE.value,
                    "description": "Core payment processing service",
                    "tags": ["payment", "critical", "prod"],
                    "cloud_provider": "gcp"
                },
                {
                    "application_name": "User Service",
                    "github_repo": "myorg/user-service",
                    "gcp_project_id": "prod-user-svc-002",
                    "argocd_app_name": "user-service-prod",
                    "grafana_dashboard": "User Service Metrics",
                    "gke_cluster_name": "prod-cluster-us-east1",
                    "namespace": "user-prod",
                    "application_owner": "admin",
                    "status": ApplicationStatus.ACTIVE.value,
                    "description": "User authentication and profile management",
                    "tags": ["auth", "user", "prod"],
                    "cloud_provider": "gcp"
                },
                {
                    "application_name": "Analytics Engine",
                    "github_repo": "myorg/analytics-engine",
                    "gcp_project_id": "staging-analytics-003",
                    "argocd_app_name": "analytics-engine-staging",
                    "grafana_dashboard": "Analytics Performance",
                    "gke_cluster_name": "staging-cluster-us-west1",
                    "namespace": "analytics-staging",
                    "application_owner": "admin",
                    "status": ApplicationStatus.INACTIVE.value,
                    "description": "Real-time analytics processing pipeline",
                    "tags": ["analytics", "staging", "data"],
                    "cloud_provider": "gcp"
                }
            ]
            
            for app_data in demo_apps:
                app_id = str(uuid.uuid4())
                app_data["id"] = app_id
                app_data["created_at"] = datetime.now().isoformat()
                app_data["updated_at"] = datetime.now().isoformat()
                self.collection.document(app_id).set(app_data, timeout=8)

            logger.info(f"[OK] Created {len(demo_apps)} demo applications in Firestore")
            
        except Exception as e:
            logger.error(f"[FAIL] Error creating demo applications: {e}")
    
    # ==================== CREATE OPERATIONS ====================
    
    # Fields the server owns; a caller can never set these directly.
    SERVER_CONTROLLED_FIELDS = {"id", "created_at", "updated_at", "updated_by"}

    def create_application(self, app_data: Dict) -> Dict:
        """Create a new application, persisting every field supplied by the caller."""
        try:
            app_id = str(uuid.uuid4())
            now = datetime.now().isoformat()

            # Persist all caller-supplied fields (ApplicationCreate carries 34 of them)
            # instead of a hand-picked subset, dropping only server-controlled keys.
            application = {
                key: value for key, value in app_data.items()
                if key not in self.SERVER_CONTROLLED_FIELDS
            }

            # Firestore stores plain scalars, so unwrap any enum members
            for enum_field in ("status", "cloud_provider"):
                value = application.get(enum_field)
                if hasattr(value, "value"):
                    application[enum_field] = value.value

            # Defaults for optional/absent values
            if application.get("status") is None:
                application["status"] = ApplicationStatus.ACTIVE.value
            if application.get("cloud_provider") is None:
                application["cloud_provider"] = "azure"
            if application.get("tags") is None:
                application["tags"] = []
            if application.get("custom_metadata") is None:
                application["custom_metadata"] = []

            # Server-controlled fields are authoritative
            application["id"] = app_id
            application["created_by"] = app_data.get("created_by") or "system"
            application["created_at"] = now
            application["updated_at"] = now

            self.collection.document(app_id).set(application)
            
            logger.info(f"[OK] Created application: {app_data.get('application_name')} (ID: {app_id})")
            return application
            
        except Exception as e:
            logger.error(f"[FAIL] Error creating application: {e}")
            raise
    
    # ==================== READ OPERATIONS ====================
    
    def get_application(self, app_id: str) -> Optional[Dict]:
        """Get application by ID."""
        try:
            doc = self.collection.document(app_id).get()
            if doc.exists:
                return doc.to_dict()
            return None
        except Exception as e:
            logger.error(f"Error getting application {app_id}: {e}")
            return None
    
    def get_application_by_name(self, app_name: str) -> Optional[Dict]:
        """Get application by name (case-insensitive approximation)."""
        try:
            # Firestore doesn't do native case-insensitive search easily, using exact match for now
            docs = self.collection.where(filter=FieldFilter("application_name", "==", app_name)).limit(1).get()
            for doc in docs:
                return doc.to_dict()
            
            # Try getting all and filtering in memory as fallback (not scalable, but works for small sets)
            all_docs = self.collection.stream()
            for doc in all_docs:
                data = doc.to_dict()
                if data.get("application_name", "").lower() == app_name.lower():
                    return data
            return None
        except Exception as e:
            logger.error(f"Error getting application by name {app_name}: {e}")
            return None
    
    def get_all_applications(
        self,
        status: Optional[str] = None,
        cluster: Optional[str] = None,
        skip: int = 0,
        limit: int = 100
    ) -> Tuple[List[Dict], int]:
        """Get all applications with optional filtering and pagination."""
        try:
            query = self.collection
            
            if status:
                query = query.where(filter=FieldFilter("status", "==", status))
            if cluster:
                query = query.where(filter=FieldFilter("gke_cluster_name", "==", cluster))
                
            # Note: Firestore count queries are special, here we just get all matching for count
            # In a prod environment, you'd use aggregation queries for counts
            all_matching = list(query.stream())
            total = len(all_matching)
            
            # Order by created_at desc, sort in memory for simplicity due to index requirements in firestore
            all_matching_dicts = [doc.to_dict() for doc in all_matching]
            all_matching_dicts.sort(key=lambda x: x.get("created_at", ""), reverse=True)
            
            result = all_matching_dicts[skip:skip+limit]
            
            return result, total
            
        except Exception as e:
            logger.error(f"Error getting applications: {e}")
            return [], 0
    
    def list_applications(
        self,
        status: Optional[str] = None,
        owner: Optional[str] = None,
        cluster: Optional[str] = None,
        skip: int = 0,
        limit: int = 100
    ) -> Tuple[List[Dict], int]:
        """List applications with optional filtering and pagination."""
        try:
            query = self.collection
            
            if status:
                query = query.where(filter=FieldFilter("status", "==", status))
            if owner:
                query = query.where(filter=FieldFilter("application_owner", "==", owner))
            if cluster:
                query = query.where(filter=FieldFilter("gke_cluster_name", "==", cluster))
                
            all_matching = list(query.stream())
            total = len(all_matching)
            
            all_matching_dicts = [doc.to_dict() for doc in all_matching]
            all_matching_dicts.sort(key=lambda x: x.get("created_at", ""), reverse=True)
            
            result = all_matching_dicts[skip:skip+limit]
            
            return result, total
            
        except Exception as e:
            logger.error(f"Error listing applications: {e}")
            return [], 0
    
    def search_applications(self, query_text: str, limit: int = 20) -> List[Dict]:
        """Search applications by name or description."""
        try:
            # Firestore lacks native text search. In memory filtering.
            search_term = query_text.lower()
            all_docs = self.collection.stream()
            results = []
            
            for doc in all_docs:
                data = doc.to_dict()
                name = data.get("application_name", "").lower()
                desc = data.get("description", "").lower()
                
                if search_term in name or search_term in desc:
                    results.append(data)
                    if len(results) >= limit:
                        break
            
            return results
            
        except Exception as e:
            logger.error(f"Error searching applications: {e}")
            return []
    
    def get_applications_by_owner(self, owner: str) -> List[Dict]:
        """Get all applications owned by a user."""
        try:
            docs = self.collection.where(filter=FieldFilter("application_owner", "==", owner)).stream()
            result = [doc.to_dict() for doc in docs]
            result.sort(key=lambda x: x.get("created_at", ""), reverse=True)
            return result
        except Exception as e:
            logger.error(f"Error getting applications by owner {owner}: {e}")
            return []
    
    def get_applications_by_cluster(self, cluster: str) -> List[Dict]:
        """Get all applications in a specific cluster."""
        try:
            docs = self.collection.where(filter=FieldFilter("gke_cluster_name", "==", cluster)).stream()
            result = [doc.to_dict() for doc in docs]
            result.sort(key=lambda x: x.get("created_at", ""), reverse=True)
            return result
        except Exception as e:
            logger.error(f"Error getting applications by cluster {cluster}: {e}")
            return []
    
    def get_applications_by_status(self, status: str) -> List[Dict]:
        """Get all applications with a specific status."""
        try:
            docs = self.collection.where(filter=FieldFilter("status", "==", status)).stream()
            result = [doc.to_dict() for doc in docs]
            result.sort(key=lambda x: x.get("created_at", ""), reverse=True)
            return result
        except Exception as e:
            logger.error(f"Error getting applications by status {status}: {e}")
            return []
    
    # ==================== UPDATE OPERATIONS ====================
    
    def update_application(self, app_id: str, user_id: str, updates: Dict) -> Optional[Dict]:
        """Update application details."""
        try:
            doc_ref = self.collection.document(app_id)
            doc = doc_ref.get()
            
            if not doc.exists:
                logger.warning(f"Application {app_id} not found")
                return None
            
            filtered_updates = {k: v for k, v in updates.items() if k not in ['id', 'created_at']}
            filtered_updates['updated_by'] = user_id
            filtered_updates['updated_at'] = datetime.now().isoformat()
            
            doc_ref.update(filtered_updates)
            
            # Fetch updated document
            updated_doc = doc_ref.get().to_dict()
            logger.info(f"[OK] Updated application: {app_id}")
            return updated_doc
            
        except Exception as e:
            logger.error(f"[FAIL] Error updating application {app_id}: {e}")
            raise
    
    def toggle_status(self, app_id: str, user_id: str) -> Optional[Dict]:
        """Toggle application status between active and inactive."""
        try:
            doc_ref = self.collection.document(app_id)
            doc = doc_ref.get()
            
            if not doc.exists:
                logger.warning(f"Application {app_id} not found")
                return None
            
            app_data = doc.to_dict()
            current_status = app_data.get("status")
            
            new_status = ApplicationStatus.INACTIVE.value if current_status == ApplicationStatus.ACTIVE.value else ApplicationStatus.ACTIVE.value
            
            updates = {
                "status": new_status,
                "updated_by": user_id,
                "updated_at": datetime.now().isoformat()
            }
            
            doc_ref.update(updates)
            
            # Fetch updated document
            updated_doc = doc_ref.get().to_dict()
            logger.info(f"[OK] Toggled status for application: {app_id} to {new_status}")
            return updated_doc
            
        except Exception as e:
            logger.error(f"[FAIL] Error toggling status for application {app_id}: {e}")
            raise
    
    # ==================== DELETE OPERATIONS ====================
    
    def delete_application(self, app_id: str) -> bool:
        """Delete an application."""
        try:
            doc_ref = self.collection.document(app_id)
            if not doc_ref.get().exists:
                logger.warning(f"Application {app_id} not found")
                return False
            
            doc_ref.delete()
            logger.info(f"[OK] Deleted application: {app_id}")
            return True
            
        except Exception as e:
            logger.error(f"[FAIL] Error deleting application {app_id}: {e}")
            return False
    
    # ==================== STATISTICS ====================
    
    def get_statistics(self) -> ApplicationStats:
        """Get application statistics."""
        try:
            all_docs = list(self.collection.stream())
            total = len(all_docs)
            
            active = 0
            inactive = 0
            pending = 0
            suspended = 0
            
            applications_by_owner = {}
            applications_by_cluster = {}
            
            # Recent applications (last 7 days)
            from datetime import timedelta
            seven_days_ago = datetime.now() - timedelta(days=7)
            recent = 0
            
            for doc in all_docs:
                data = doc.to_dict()
                status = data.get("status")
                
                if status == ApplicationStatus.ACTIVE.value:
                    active += 1
                elif status == ApplicationStatus.INACTIVE.value:
                    inactive += 1
                elif status == ApplicationStatus.PENDING.value:
                    pending += 1
                elif status == ApplicationStatus.SUSPENDED.value:
                    suspended += 1
                
                owner = data.get("application_owner")
                if owner:
                    applications_by_owner[owner] = applications_by_owner.get(owner, 0) + 1
                    
                cluster = data.get("gke_cluster_name")
                if cluster:
                    applications_by_cluster[cluster] = applications_by_cluster.get(cluster, 0) + 1
                    
                created_at_str = data.get("created_at")
                if created_at_str:
                    try:
                        created_at = datetime.fromisoformat(created_at_str)
                        if created_at >= seven_days_ago:
                            recent += 1
                    except ValueError:
                        pass
            
            return ApplicationStats(
                total_applications=total,
                active_applications=active,
                inactive_applications=inactive,
                pending_applications=pending,
                suspended_applications=suspended,
                applications_by_owner=applications_by_owner,
                applications_by_cluster=applications_by_cluster,
                recent_applications=recent
            )
            
        except Exception as e:
            logger.error(f"Error getting statistics: {e}")
            return ApplicationStats(
                total_applications=0,
                active_applications=0,
                inactive_applications=0,
                pending_applications=0,
                suspended_applications=0,
                applications_by_owner={},
                applications_by_cluster={},
                recent_applications=0
            )


    def get_application_with_users(self, app_id: str) -> Optional[Dict]:
        app = self.get_application(app_id)
        if not app:
            return None
        return self._resolve_users_for_app(app)

    def list_applications_with_users(
        self,
        status: Optional[str] = None,
        owner: Optional[str] = None,
        cluster: Optional[str] = None,
        skip: int = 0,
        limit: int = 100
    ) -> Tuple[List[Dict], int]:
        apps, total = self.list_applications(status, owner, cluster, skip, limit)
        apps_with_users = [self._resolve_users_for_app(app) for app in apps]
        return apps_with_users, total

    def search_applications_with_users(self, query_text: str, limit: int = 20) -> List[Dict]:
        apps = self.search_applications(query_text, limit)
        return [self._resolve_users_for_app(app) for app in apps]

    def _resolve_users_for_app(self, app: Dict) -> Dict:
        from app.auth.database_firestore import user_db
        creator = None
        updater = None
        if app.get('created_by'):
            creator = user_db.get_user_by_id(app['created_by'])
        if app.get('updated_by'):
            updater = user_db.get_user_by_id(app['updated_by'])
            
        return {
            "Application": app,
            "creator_username": creator.get("username") if creator else None,
            "creator_email": creator.get("email") if creator else None,
            "updater_username": updater.get("username") if updater else None,
            "updater_email": updater.get("email") if updater else None,
        }
    
    def invalidate_cache(self, app_id: str = None):
        pass # No-op for firestore since cache is not implemented here yet

# Global database instance
application_db = ApplicationDatabase()
