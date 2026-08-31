"""
Admin API routes for metadata management.

Provides REST endpoints for managing application metadata with admin authentication.
All endpoints require admin role.
"""
import logging
from fastapi import APIRouter, HTTPException, Depends, Query, status
from typing import Optional, List

from app.metadata.schemas import (
    CreateMetadataRequest, UpdateMetadataRequest, MetadataResponse,
    ConfiguredIntegrationsResponse, SearchResultResponse,
    ErrorResponse, SuccessResponse
)
from app.metadata.service import MetadataService
from app.auth.dependencies import get_current_admin_user
from app.auth.models import UserResponse

# Import verify_admin_token as alias for backward compatibility
verify_admin_token = get_current_admin_user

logger = logging.getLogger(__name__)

# Create router for metadata endpoints
router = APIRouter(
    prefix="/api/v1/metadata",
    tags=["metadata"]
)


@router.post(
    "",
    response_model=SuccessResponse,
    responses={400: {"model": ErrorResponse}, 401: {"model": ErrorResponse}},
    summary="Create application metadata",
    description="Create metadata for a new application. Admin only.",
    dependencies=[Depends(verify_admin_token)]
)
async def create_metadata(
    request: CreateMetadataRequest,
    current_user: dict = Depends(verify_admin_token)
) -> SuccessResponse:
    """
    Create new application metadata.
    
    - **app_name**: Unique application identifier (required)
    - **description**: Application description
    - **environment**: production, staging, development, qa, or test
    - **team**: Team responsible for the application
    - **github**: GitHub repository configuration
    - **argocd**: ArgoCD application configuration
    - **grafana**: Grafana dashboard configuration
    - **cost**: Cost tracking configuration
    - **tags**: List of tags for categorization
    
    Requires admin authentication.
    """
    try:
        logger.info(f"Creating metadata for {request.app_name} by {current_user.username}")
        
        success, error = MetadataService.add_metadata(
            app_name=request.app_name,
            description=request.description,
            environment=request.environment,
            team=request.team,
            github=request.github.dict() if request.github else None,
            argocd=request.argocd.dict() if request.argocd else None,
            grafana=request.grafana.dict() if request.grafana else None,
            cost=request.cost.dict() if request.cost else None,
            tags=request.tags,
            created_by=current_user.username
        )
        
        if success:
            return SuccessResponse(
                success=True,
                message=f"Metadata created successfully for {request.app_name}",
                data={"app_name": request.app_name}
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=error
            )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating metadata: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Internal server error: {str(e)}"
        )


@router.get(
    "",
    response_model=List[MetadataResponse],
    responses={401: {"model": ErrorResponse}},
    summary="List all application metadata",
    description="Retrieve metadata for all registered applications. Admin only.",
    dependencies=[Depends(verify_admin_token)]
)
async def list_metadata(
    current_user: dict = Depends(verify_admin_token)
) -> List[MetadataResponse]:
    """
    List all application metadata.
    
    Returns metadata for all registered applications with their integration configurations.
    Results are cached for 5 minutes for performance.
    
    Requires admin authentication.
    """
    try:
        logger.info(f"Listing all metadata requested by {current_user.username}")
        
        metadata_list = MetadataService.list_all_metadata(use_cache=True)
        
        return [
            MetadataResponse(
                app_name=m.app_name,
                description=m.description,
                environment=m.environment,
                team=m.team,
                github={
                    "enabled": m.github.enabled,
                    "repo_owner": m.github.repo_owner,
                    "repo_name": m.github.repo_name,
                    "branch": m.github.branch,
                    "repo_url": m.github.repo_url
                },
                argocd={
                    "enabled": m.argocd.enabled,
                    "app_name": m.argocd.app_name,
                    "project": m.argocd.project,
                    "namespace": m.argocd.namespace,
                    "server": m.argocd.server
                },
                grafana={
                    "enabled": m.grafana.enabled,
                    "dashboard_id": m.grafana.dashboard_id,
                    "dashboard_url": m.grafana.dashboard_url,
                    "datasource": m.grafana.datasource,
                    "alert_uid": m.grafana.alert_uid
                },
                cost={
                    "enabled": m.cost.enabled,
                    "cost_center": m.cost.cost_center,
                    "budget_alert_threshold": m.cost.budget_alert_threshold,
                    "tags": m.cost.tags
                },
                created_at=m.created_at,
                updated_at=m.updated_at,
                created_by=m.created_by,
                updated_by=m.updated_by,
                tags=m.tags
            )
            for m in metadata_list
        ]
    
    except Exception as e:
        logger.error(f"Error listing metadata: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Internal server error: {str(e)}"
        )


@router.get(
    "/{app_name}",
    response_model=MetadataResponse,
    responses={401: {"model": ErrorResponse}, 404: {"model": ErrorResponse}},
    summary="Get application metadata",
    description="Retrieve metadata for a specific application. Admin only.",
    dependencies=[Depends(verify_admin_token)]
)
async def get_metadata(
    app_name: str,
    current_user: dict = Depends(verify_admin_token)
) -> MetadataResponse:
    """
    Get metadata for a specific application.
    
    - **app_name**: Application name (path parameter)
    
    Returns complete metadata including all integration configurations.
    Results are cached for 5 minutes for performance.
    
    Requires admin authentication.
    """
    try:
        logger.info(f"Getting metadata for {app_name} requested by {current_user.username}")
        
        metadata = MetadataService.get_metadata(app_name, use_cache=True)
        
        if not metadata:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Metadata not found for application: {app_name}"
            )
        
        return MetadataResponse(
            app_name=metadata.app_name,
            description=metadata.description,
            environment=metadata.environment,
            team=metadata.team,
            github={
                "enabled": metadata.github.enabled,
                "repo_owner": metadata.github.repo_owner,
                "repo_name": metadata.github.repo_name,
                "branch": metadata.github.branch,
                "repo_url": metadata.github.repo_url
            },
            argocd={
                "enabled": metadata.argocd.enabled,
                "app_name": metadata.argocd.app_name,
                "project": metadata.argocd.project,
                "namespace": metadata.argocd.namespace,
                "server": metadata.argocd.server
            },
            grafana={
                "enabled": metadata.grafana.enabled,
                "dashboard_id": metadata.grafana.dashboard_id,
                "dashboard_url": metadata.grafana.dashboard_url,
                "datasource": metadata.grafana.datasource,
                "alert_uid": metadata.grafana.alert_uid
            },
            cost={
                "enabled": metadata.cost.enabled,
                "cost_center": metadata.cost.cost_center,
                "budget_alert_threshold": metadata.cost.budget_alert_threshold,
                "tags": metadata.cost.tags
            },
            created_at=metadata.created_at,
            updated_at=metadata.updated_at,
            created_by=metadata.created_by,
            updated_by=metadata.updated_by,
            tags=metadata.tags
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting metadata: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Internal server error: {str(e)}"
        )


@router.put(
    "/{app_name}",
    response_model=SuccessResponse,
    responses={400: {"model": ErrorResponse}, 401: {"model": ErrorResponse}, 404: {"model": ErrorResponse}},
    summary="Update application metadata",
    description="Update metadata for an existing application. Admin only.",
    dependencies=[Depends(verify_admin_token)]
)
async def update_metadata(
    app_name: str,
    request: UpdateMetadataRequest,
    current_user: dict = Depends(verify_admin_token)
) -> SuccessResponse:
    """
    Update metadata for an existing application.
    
    - **app_name**: Application name (path parameter)
    - Any fields in the request body will be updated (null fields are skipped)
    
    Returns success status and updated application name.
    Cache is automatically invalidated for this application.
    
    Requires admin authentication.
    """
    try:
        logger.info(f"Updating metadata for {app_name} by {current_user.username}")
        
        # Build update dict with only provided fields
        update_dict = {}
        
        if request.description is not None:
            update_dict["description"] = request.description
        if request.environment is not None:
            update_dict["environment"] = request.environment
        if request.team is not None:
            update_dict["team"] = request.team
        if request.tags is not None:
            update_dict["tags"] = request.tags
        if request.github is not None:
            update_dict["github"] = request.github.dict()
        if request.argocd is not None:
            update_dict["argocd"] = request.argocd.dict()
        if request.grafana is not None:
            update_dict["grafana"] = request.grafana.dict()
        if request.cost is not None:
            update_dict["cost"] = request.cost.dict()
        
        success, error = MetadataService.update_metadata(
            app_name=app_name,
            updated_by=current_user.username,
            **update_dict
        )
        
        if success:
            return SuccessResponse(
                success=True,
                message=f"Metadata updated successfully for {app_name}",
                data={"app_name": app_name}
            )
        else:
            status_code = status.HTTP_404_NOT_FOUND if "not found" in error.lower() else status.HTTP_400_BAD_REQUEST
            raise HTTPException(
                status_code=status_code,
                detail=error
            )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating metadata: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Internal server error: {str(e)}"
        )


@router.delete(
    "/{app_name}",
    response_model=SuccessResponse,
    responses={401: {"model": ErrorResponse}, 404: {"model": ErrorResponse}},
    summary="Delete application metadata",
    description="Delete metadata for an application. Admin only.",
    dependencies=[Depends(verify_admin_token)]
)
async def delete_metadata(
    app_name: str,
    current_user: dict = Depends(verify_admin_token)
) -> SuccessResponse:
    """
    Delete metadata for an application.
    
    - **app_name**: Application name (path parameter)
    
    Permanently removes all metadata for the specified application.
    Cache is automatically invalidated.
    
    Requires admin authentication.
    """
    try:
        logger.info(f"Deleting metadata for {app_name} by {current_user.username}")
        
        success, error = MetadataService.delete_metadata(app_name)
        
        if success:
            return SuccessResponse(
                success=True,
                message=f"Metadata deleted successfully for {app_name}",
                data={"app_name": app_name}
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=error
            )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting metadata: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Internal server error: {str(e)}"
        )


@router.get(
    "/search/query",
    response_model=List[SearchResultResponse],
    responses={401: {"model": ErrorResponse}},
    summary="Search application metadata",
    description="Search metadata by keyword. Admin only.",
    dependencies=[Depends(verify_admin_token)]
)
async def search_metadata(
    q: str = Query(..., min_length=1, description="Search query"),
    current_user: dict = Depends(verify_admin_token)
) -> List[SearchResultResponse]:
    """
    Search metadata by keyword.
    
    - **q**: Search query (required, minimum 1 character)
    
    Searches across app name, description, team, and tags.
    Returns matching applications with summary information.
    
    Requires admin authentication.
    """
    try:
        logger.info(f"Searching metadata for '{q}' by {current_user.username}")
        
        results = MetadataService.search_metadata(q, use_cache=False)
        
        return [
            SearchResultResponse(
                app_name=m.app_name,
                description=m.description,
                team=m.team,
                environment=m.environment
            )
            for m in results
        ]
    
    except Exception as e:
        logger.error(f"Error searching metadata: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Internal server error: {str(e)}"
        )


@router.get(
    "/{app_name}/integrations",
    response_model=ConfiguredIntegrationsResponse,
    responses={401: {"model": ErrorResponse}, 404: {"model": ErrorResponse}},
    summary="Get configured integrations",
    description="Get list of enabled integrations for an application. Admin only.",
    dependencies=[Depends(verify_admin_token)]
)
async def get_configured_integrations(
    app_name: str,
    current_user: dict = Depends(verify_admin_token)
) -> ConfiguredIntegrationsResponse:
    """
    Get configured (enabled) integrations for an application.
    
    - **app_name**: Application name (path parameter)
    
    Returns which integrations (GitHub, ArgoCD, Grafana, Cost) are enabled.
    Useful for determining which sub-agents to invoke.
    
    Requires admin authentication.
    """
    try:
        logger.info(f"Getting integrations for {app_name} requested by {current_user.username}")
        
        integrations = MetadataService.get_configured_integrations(app_name)
        
        if not integrations:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No metadata found for application: {app_name}"
            )
        
        return ConfiguredIntegrationsResponse(
            app_name=app_name,
            github=integrations.get("github", False),
            argocd=integrations.get("argocd", False),
            grafana=integrations.get("grafana", False),
            cost=integrations.get("cost", False)
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting integrations: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Internal server error: {str(e)}"
        )
