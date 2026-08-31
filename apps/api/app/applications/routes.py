from fastapi import APIRouter, Depends, HTTPException, status, Query
from typing import List, Optional
import math
import uuid
import os
from ..auth.dependencies import get_current_user, get_current_admin_user, get_current_admin_or_team_lead
from ..auth.models import UserResponse
from ..auth.database_firestore import user_db
from .models import (
    ApplicationCreate, ApplicationUpdate, ApplicationResponse, 
    ApplicationListResponse, ApplicationStats, ApplicationStatus,
    ApplicationSearchQuery
)
from .database_firestore import application_db
from .database_firestore import application_db as optimized_application_db
import logging

logger = logging.getLogger(__name__)
router = APIRouter()

# Feature flag for optimized queries
USE_OPTIMIZED_QUERIES = os.getenv("USE_OPTIMIZED_QUERIES", "false").lower() == "true"

if USE_OPTIMIZED_QUERIES:
    logger.info("[OK] Using optimized database queries with JOIN and caching")
else:
    logger.info("[INFO] Using standard database queries (set USE_OPTIMIZED_QUERIES=true to enable optimization)")

# Helper function to build application response (for optimized path)
def build_application_response_optimized(app: dict) -> ApplicationResponse:
    """Build ApplicationResponse from app dict with pre-fetched user data (no additional queries)."""
    try:
        # User data already fetched via JOIN
        created_by_username = app.get("created_by_username", "system")
        updated_by_username = app.get("updated_by_username")
        
        # Safely handle cloud_provider enum conversion
        cloud_provider = app.get("cloud_provider", "gcp")
        if isinstance(cloud_provider, str):
            cloud_provider = cloud_provider.lower()
            if cloud_provider not in ["gcp", "azure", "aws"]:
                cloud_provider = "gcp"
        
        # Safely handle status enum conversion
        status = app.get("status", "active")
        if isinstance(status, str):
            status = status.lower()
            if status not in ["active", "inactive", "pending", "suspended"]:
                status = "active"
        
        # Ensure custom_metadata is a list of dicts
        custom_metadata = app.get("custom_metadata", [])
        if not isinstance(custom_metadata, list):
            custom_metadata = []
        
        # Convert datetime objects to ISO strings
        created_at = app.get("created_at")
        updated_at = app.get("updated_at")
        
        if created_at and hasattr(created_at, 'isoformat'):
            created_at = created_at.isoformat()
        if updated_at and hasattr(updated_at, 'isoformat'):
            updated_at = updated_at.isoformat()
        
        return ApplicationResponse(
            id=app.get("id") or str(uuid.uuid4()),
            application_name=app.get("application_name"),
            github_repo=app.get("github_repo"),
            argocd_app_name=app.get("argocd_app_name"),
            grafana_dashboard=app.get("grafana_dashboard"),
            grafana_alert_name=app.get("grafana_alert_name"),
            grafana_dashboard_url=app.get("grafana_dashboard_url"),
            grafana_alert=app.get("grafana_alert"),
            application_owner=app.get("application_owner"),
            status=status,
            description=app.get("description"),
            application_criticality=app.get("application_criticality"),
            custom_metadata=custom_metadata,
            cloud_provider=cloud_provider,
            gcp_project_id=app.get("gcp_project_id"),
            gke_cluster_name=app.get("gke_cluster_name"),
            namespace=app.get("namespace", "default"),
            gcp_log_resource=app.get("gcp_log_resource"),
            deployment_name=app.get("deployment_name"),
            pod_name=app.get("pod_name"),
            azure_subscription_id=app.get("azure_subscription_id"),
            aks_cluster_name=app.get("aks_cluster_name"),
            azure_deployment_name=app.get("azure_deployment_name"),
            azure_pod_name=app.get("azure_pod_name"),
            azure_namespace=app.get("azure_namespace"),
            resource_group=app.get("resource_group"),
            workspace=app.get("workspace"),
            workspace_resource_group=app.get("workspace_resource_group"),
            ingress_name=app.get("ingress_name"),
            ingress_public_ip=app.get("ingress_public_ip"),
            ingress_namespace=app.get("ingress_namespace"),
            aws_account_id=app.get("aws_account_id"),
            eks_cluster_name=app.get("eks_cluster_name"),
            cloudwatch_log_group_path=app.get("cloudwatch_log_group_path"),
            aws_deployment_name=app.get("aws_deployment_name"),
            aws_pod_name=app.get("aws_pod_name"),
            aws_namespace=app.get("aws_namespace"),
            created_by=app.get("created_by"),
            created_by_username=created_by_username,
            updated_by=app.get("updated_by"),
            updated_by_username=updated_by_username,
            created_at=created_at,
            updated_at=updated_at
        )
    except Exception as e:
        logger.error(f"Error building optimized response: {e}", exc_info=True)
        raise

# Helper function to build application response (original implementation)
def build_application_response(app: dict) -> ApplicationResponse:
    """Build ApplicationResponse from database record."""
    try:
        created_by = app.get("created_by", "system")
        updated_by = app.get("updated_by")
        
        created_by_user = None
        updated_by_user = None
        
        try:
            created_by_user = user_db.get_user_by_id(created_by) if created_by != "system" else None
        except Exception as e:
            logger.warning(f"Could not fetch user {created_by}: {e}")
            
        try:
            updated_by_user = user_db.get_user_by_id(updated_by) if updated_by and updated_by != "system" else None
        except Exception as e:
            logger.warning(f"Could not fetch user {updated_by}: {e}")
        
        # Safely handle cloud_provider enum conversion
        cloud_provider = app.get("cloud_provider", "gcp")
        if isinstance(cloud_provider, str):
            cloud_provider = cloud_provider.lower()
            if cloud_provider not in ["gcp", "azure", "aws"]:
                cloud_provider = "gcp"
        
        # Safely handle status enum conversion
        status = app.get("status", "active")
        if isinstance(status, str):
            status = status.lower()
            if status not in ["active", "inactive", "pending", "suspended"]:
                status = "active"
        
        # Ensure custom_metadata is a list of dicts
        custom_metadata = app.get("custom_metadata", [])
        if not isinstance(custom_metadata, list):
            custom_metadata = []
        
        # Convert datetime objects to ISO strings
        created_at = app.get("created_at")
        updated_at = app.get("updated_at")
        
        if created_at and hasattr(created_at, 'isoformat'):
            created_at = created_at.isoformat()
        if updated_at and hasattr(updated_at, 'isoformat'):
            updated_at = updated_at.isoformat()
        
        # Safely extract username from user objects
        created_by_username = "system"
        if created_by_user:
            if isinstance(created_by_user, dict):
                created_by_username = created_by_user.get("username", "system")
            else:
                created_by_username = getattr(created_by_user, "username", "system")
        
        updated_by_username = None
        if updated_by_user:
            if isinstance(updated_by_user, dict):
                updated_by_username = updated_by_user.get("username")
            else:
                updated_by_username = getattr(updated_by_user, "username", None)
        
        return ApplicationResponse(
            id=app.get("id") or str(app.get("_id", "")) or str(uuid.uuid4()),
            application_name=app.get("application_name"),
            github_repo=app.get("github_repo"),
            argocd_app_name=app.get("argocd_app_name"),
            grafana_dashboard=app.get("grafana_dashboard"),
            grafana_alert_name=app.get("grafana_alert_name"),
            grafana_dashboard_url=app.get("grafana_dashboard_url"),
            grafana_alert=app.get("grafana_alert"),
            application_owner=app.get("application_owner"),
            status=status,
            description=app.get("description"),
            application_criticality=app.get("application_criticality"),
            custom_metadata=custom_metadata,
            cloud_provider=cloud_provider,
            # Legacy GCP fields
            gcp_project_id=app.get("gcp_project_id"),
            gke_cluster_name=app.get("gke_cluster_name"),
            namespace=app.get("namespace", "default"),
            # GCP specific
            gcp_log_resource=app.get("gcp_log_resource"),
            deployment_name=app.get("deployment_name"),
            pod_name=app.get("pod_name"),
            # Azure specific
            azure_subscription_id=app.get("azure_subscription_id"),
            aks_cluster_name=app.get("aks_cluster_name"),
            azure_deployment_name=app.get("azure_deployment_name"),
            azure_pod_name=app.get("azure_pod_name"),
            azure_namespace=app.get("azure_namespace"),
            resource_group=app.get("resource_group"),
            workspace=app.get("workspace"),
            workspace_resource_group=app.get("workspace_resource_group"),
            ingress_name=app.get("ingress_name"),
            ingress_public_ip=app.get("ingress_public_ip"),
            ingress_namespace=app.get("ingress_namespace"),
            # AWS specific
            aws_account_id=app.get("aws_account_id"),
            eks_cluster_name=app.get("eks_cluster_name"),
            cloudwatch_log_group_path=app.get("cloudwatch_log_group_path"),
            aws_deployment_name=app.get("aws_deployment_name"),
            aws_pod_name=app.get("aws_pod_name"),
            aws_namespace=app.get("aws_namespace"),
            # Metadata
            created_by=created_by,
            created_by_username=created_by_username,
            updated_by=updated_by,
            updated_by_username=updated_by_username,
            created_at=created_at,
            updated_at=updated_at
        )
    except Exception as e:
        logger.error(f"Error building response for app {app.get('_id', 'unknown')}: {e}", exc_info=True)
        raise

# Create new application
@router.post("/", response_model=ApplicationResponse, status_code=status.HTTP_201_CREATED)
async def create_application(
    app_data: ApplicationCreate,
    current_user: UserResponse = Depends(get_current_admin_or_team_lead)
):
    """
    Create a new application for SRE agent monitoring.
    
    Requires: Admin or Team Lead role
    """
    try:
        app_dict = app_data.model_dump()
        # Add created_by to the app_dict before creating
        app_dict["created_by"] = current_user.id
        application = application_db.create_application(app_dict)
        
        # Invalidate cache if using optimized queries
        if USE_OPTIMIZED_QUERIES:
            optimized_application_db.invalidate_cache()
        
        # Use appropriate response builder
        if USE_OPTIMIZED_QUERIES and application:
            app_with_users = optimized_application_db.get_application_with_users(application['id'])
            return build_application_response_optimized(app_with_users)
        else:
            return build_application_response(application)
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error creating application: {e}")
        raise HTTPException(status_code=500, detail="Failed to create application")

# Get all applications (with pagination and filtering)
@router.get("/", response_model=ApplicationListResponse)
async def list_applications(
    page: Optional[int] = Query(None, ge=1, description="Page number"),
    page_size: Optional[int] = Query(None, ge=1, le=1000, description="Items per page"),
    # Frontend-contract aliases; kept in sync with page/page_size.
    limit: Optional[int] = Query(None, ge=1, le=1000, description="Alias for page_size"),
    status_param: Optional[str] = Query(None, alias="status", description="Filter by status (case-insensitive)"),
    owner: Optional[str] = Query(None, description="Filter by owner"),
    cluster: Optional[str] = Query(None, description="Filter by cluster name"),
    current_user: UserResponse = Depends(get_current_user)
):
    """
    Get list of all applications with pagination and filtering.

    Accepts both (page, page_size) and (skip-less) limit aliases so frontend
    clients using ?limit=N work identically. `status` is case-insensitive.

    Regular users can view all applications.
    """
    try:
        effective_page_size = page_size or limit or 20
        effective_page = page or 1
        skip = (effective_page - 1) * effective_page_size

        # Normalize status case before enum validation ("ACTIVE" == "active").
        status_filter = None
        if status_param:
            try:
                status_filter = ApplicationStatus(status_param.strip().lower())
            except ValueError:
                raise HTTPException(
                    status_code=422,
                    detail=f"Invalid status '{status_param}'. Valid values: "
                           f"{[s.value for s in ApplicationStatus]}"
                )
        
        # Use optimized queries if enabled
        if USE_OPTIMIZED_QUERIES:
            try:
                applications, total_count = optimized_application_db.list_applications_with_users(
                    status=status_filter,
                    owner=owner,
                    cluster=cluster,
                    skip=skip,
                    limit=effective_page_size
                )
                # Use optimized response builder (no additional DB queries)
                app_responses = [build_application_response_optimized(app) for app in applications]
            except Exception as e:
                logger.error(f"Optimized query error, falling back to standard: {e}")
                # Fallback to standard implementation
                applications, total_count = application_db.list_applications(
                    status=status_filter,
                    owner=owner,
                    cluster=cluster,
                    skip=skip,
                    limit=effective_page_size
                )
                app_responses = [build_application_response(app) for app in applications]
        else:
            # Standard implementation
            try:
                applications, total_count = application_db.list_applications(
                    status=status_filter,
                    owner=owner,
                    cluster=cluster,
                    skip=skip,
                    limit=effective_page_size
                )
            except Exception as e:
                logger.error(f"Database error: {e}", exc_info=True)
                raise
            
            app_responses = []
            for app in applications:
                try:
                    app_response = build_application_response(app)
                    app_responses.append(app_response)
                except Exception as e:
                    logger.error(f"Error building response for app {app.get('_id', 'unknown')}: {e}", exc_info=True)
                    logger.error(f"App data: {app}")
                    raise
        
        total_pages = math.ceil(total_count / effective_page_size) if total_count > 0 else 1
        
        return ApplicationListResponse(
            total=total_count,
            applications=app_responses,
            page=effective_page,
            page_size=effective_page_size,
            total_pages=total_pages
        )
        
    except HTTPException:
        # Preserve intentional client-error statuses (e.g. 422 invalid status
        # filter); never let them be re-wrapped as 500 below.
        raise
    except Exception as e:
        error_str = f"{type(e).__name__}: {str(e)}"
        logger.error(f"Error listing applications: {error_str}", exc_info=True)
        raise HTTPException(status_code=500, detail=error_str)

# Get single application by ID
@router.get("/{app_id}", response_model=ApplicationResponse)
async def get_application(
    app_id: str,
    current_user: UserResponse = Depends(get_current_user)
):
    """Get application details by ID."""
    try:
        # Use optimized query if enabled
        if USE_OPTIMIZED_QUERIES:
            application = optimized_application_db.get_application_with_users(app_id)
            if not application:
                raise HTTPException(status_code=404, detail="Application not found")
            return build_application_response_optimized(application)
        else:
            # Standard implementation
            application = application_db.get_application(app_id)
            if not application:
                raise HTTPException(status_code=404, detail="Application not found")
            return build_application_response(application)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting application: {e}")
        raise HTTPException(status_code=500, detail="Failed to get application")

# Update application
@router.put("/{app_id}", response_model=ApplicationResponse)
async def update_application(
    app_id: str,
    app_update: ApplicationUpdate,
    current_user: UserResponse = Depends(get_current_admin_or_team_lead)
):
    """
    Update an existing application.
    
    Requires: Admin or Team Lead role
    """
    try:
        application = application_db.get_application(app_id)
        if not application:
            raise HTTPException(status_code=404, detail="Application not found")
        
        # Only update fields that are provided
        update_dict = app_update.model_dump(exclude_unset=True)
        
        updated_app = application_db.update_application(app_id, current_user.id, update_dict)
        
        # Invalidate cache if using optimized queries
        if USE_OPTIMIZED_QUERIES:
            optimized_application_db.invalidate_cache(app_id)
        
        # Use appropriate response builder
        if USE_OPTIMIZED_QUERIES:
            # Fetch with users for optimized response
            updated_app_with_users = optimized_application_db.get_application_with_users(app_id)
            return build_application_response_optimized(updated_app_with_users)
        else:
            return build_application_response(updated_app)
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating application: {e}")
        raise HTTPException(status_code=500, detail="Failed to update application")

# Delete application
@router.delete("/{app_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_application(
    app_id: str,
    current_user: UserResponse = Depends(get_current_admin_user)
):
    """
    Delete an application.
    
    Requires: Admin role only
    """
    try:
        success = application_db.delete_application(app_id)
        
        if not success:
            raise HTTPException(status_code=404, detail="Application not found")
        
        return None
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting application: {e}")
        raise HTTPException(status_code=500, detail="Failed to delete application")

# Toggle application status
@router.post("/{app_id}/toggle", response_model=ApplicationResponse)
async def toggle_application_status(
    app_id: str,
    current_user: UserResponse = Depends(get_current_admin_or_team_lead)
):
    """
    Toggle application status between ACTIVE and INACTIVE.
    
    Requires: Admin or Team Lead role
    """
    try:
        application = application_db.toggle_status(app_id, current_user.id)
        
        if not application:
            raise HTTPException(status_code=404, detail="Application not found")
        
        return build_application_response(application)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error toggling application status: {e}")
        raise HTTPException(status_code=500, detail="Failed to toggle status")

# Search applications
@router.get("/search/query", response_model=List[ApplicationResponse])
async def search_applications(
    q: str = Query(..., min_length=1, description="Search query"),
    limit: int = Query(20, ge=1, le=100, description="Maximum results"),
    current_user: UserResponse = Depends(get_current_user)
):
    """
    Search applications by name, description, owner, repo, or tags.
    """
    try:
        # Use optimized query if enabled
        if USE_OPTIMIZED_QUERIES:
            applications = optimized_application_db.search_applications_with_users(q, limit)
            return [build_application_response_optimized(app) for app in applications]
        else:
            applications = application_db.search_applications(q, limit)
            return [build_application_response(app) for app in applications]
        
    except Exception as e:
        logger.error(f"Error searching applications: {e}")
        raise HTTPException(status_code=500, detail="Failed to search applications")

# Get application statistics
@router.get("/stats/summary", response_model=ApplicationStats)
async def get_application_stats(
    current_user: UserResponse = Depends(get_current_admin_or_team_lead)
):
    """
    Get application statistics and metrics.
    
    Requires: Admin or Team Lead role
    """
    try:
        stats = application_db.get_statistics()
        return stats
        
    except Exception as e:
        logger.error(f"Error getting application stats: {e}")
        raise HTTPException(status_code=500, detail="Failed to get statistics")

# Get applications by owner
@router.get("/owner/{owner}", response_model=List[ApplicationResponse])
async def get_applications_by_owner(
    owner: str,
    current_user: UserResponse = Depends(get_current_user)
):
    """Get all applications owned by a specific user."""
    try:
        applications = application_db.get_applications_by_owner(owner)
        
        return [build_application_response(app) for app in applications]
        
    except Exception as e:
        logger.error(f"Error getting applications by owner: {e}")
        raise HTTPException(status_code=500, detail="Failed to get applications")

# Get applications by cluster
@router.get("/cluster/{cluster_name}", response_model=List[ApplicationResponse])
async def get_applications_by_cluster(
    cluster_name: str,
    current_user: UserResponse = Depends(get_current_user)
):
    """Get all applications in a specific GKE cluster."""
    try:
        applications = application_db.get_applications_by_cluster(cluster_name)
        
        return [build_application_response(app) for app in applications]
        
    except Exception as e:
        logger.error(f"Error getting applications by cluster: {e}")
        raise HTTPException(status_code=500, detail="Failed to get applications")

# Get applications by status
@router.get("/status/{status_filter}", response_model=List[ApplicationResponse])
async def get_applications_by_status(
    status_filter: ApplicationStatus,
    current_user: UserResponse = Depends(get_current_user)
):
    """Get all applications with a specific status."""
    try:
        applications = application_db.get_applications_by_status(status_filter)
        
        return [build_application_response(app) for app in applications]
        
    except Exception as e:
        logger.error(f"Error getting applications by status: {e}")
        raise HTTPException(status_code=500, detail="Failed to get applications")
