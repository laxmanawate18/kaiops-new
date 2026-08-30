"""
Service layer for application metadata management.

Provides business logic with caching, validation, and error handling for metadata operations.
Sits between API routes and database layer.
"""
import logging
from typing import Optional, List, Dict, Any
from datetime import datetime

from app.metadata.models import ApplicationMetadata
from app.metadata.database_firestore import metadata_db
from app.metadata.cache import metadata_cache
from app.metadata.validation import MetadataValidator, ValidationError

logger = logging.getLogger(__name__)


class MetadataService:
    """Service layer for metadata operations with caching and validation."""
    
    @staticmethod
    def _coerce_dt(value: Any) -> Any:
        """
        Coerce a value into a datetime-like.

        Handles native datetimes, Firestore/Protobuf Timestamp objects, and
        ISO-8601 strings so Pydantic can build a datetime field reliably.
        """
        from datetime import datetime
        if value is None:
            return None
        if isinstance(value, datetime):
            return value
        # Firestore Timestamp (google.cloud.firestore_v1.types.Timestamp)
        if hasattr(value, "seconds") and hasattr(value, "nanos"):
            return datetime.fromtimestamp(
                value.seconds + value.nanos / 1e9
            ).replace(tzinfo=None)
        if hasattr(value, "to_datetime"):
            return value.to_datetime()
        if hasattr(value, "GetDatetime"):
            return value.GetDatetime()
        if isinstance(value, str):
            try:
                return datetime.fromisoformat(value.replace("Z", "+00:00"))
            except ValueError:
                return datetime.fromisoformat(value)
        return value
    
    @staticmethod
    def _to_model(data: Dict[str, Any]) -> ApplicationMetadata:
        """
        Convert a Firestore doc dict into an ApplicationMetadata model.

        The database stores the full Pydantic dump in ``metadata_json`` and a
        few top-level convenience fields. Prefer ``metadata_json`` for fidelity
        and overlay the flat fields as a fallback for older/tiny records.
        """
        base = data.get("metadata_json") or {}
        if not isinstance(base, dict):
            base = {}
        base = dict(base)
        
        # Overlay top-level convenience fields only where the model lacks them.
        for field in ("app_name", "description", "environment", "team", "tags"):
            if base.get(field) is None and data.get(field) is not None:
                base[field] = data[field]
        if base.get("app_name") is None:
            base["app_name"] = data.get("app_name") or data.get("application_id")
        
        # Normalize datetime fields to survive Firestore round-tripping.
        for tf in ("created_at", "updated_at"):
            if tf in base and base[tf] is not None:
                base[tf] = MetadataService._coerce_dt(base[tf])
        
        return ApplicationMetadata(**base)
    
    @staticmethod
    def get_metadata(app_name: str, use_cache: bool = True) -> Optional[ApplicationMetadata]:
        """
        Get metadata for an application with caching.
        
        Args:
            app_name: Application name
            use_cache: Whether to use cache (default: True)
            
        Returns:
            ApplicationMetadata object or None if not found
        """
        cache_key = f"metadata:{app_name}"
        
        # Try cache first
        if use_cache:
            cached_data = metadata_cache.get(cache_key)
            if cached_data is not None:
                logger.info(f"Cache hit for metadata: {app_name}")
                if isinstance(cached_data, ApplicationMetadata):
                    return cached_data
                # Older cache entries may hold a raw dict; normalize it.
                model = MetadataService._to_model(cached_data)
                metadata_cache.set(cache_key, model)
                return model
        
        # Fetch from database
        metadata = metadata_db.get_metadata(app_name)
        
        if metadata is not None:
            model = MetadataService._to_model(metadata)
            # Store in cache
            if use_cache:
                metadata_cache.set(cache_key, model)
                logger.info(f"Cached metadata for: {app_name}")
            return model
        
        return None
    
    @staticmethod
    def list_all_metadata(use_cache: bool = True) -> List[ApplicationMetadata]:
        """
        List all application metadata with caching.
        
        Args:
            use_cache: Whether to use cache (default: True)
            
        Returns:
            List of ApplicationMetadata objects
        """
        cache_key = "metadata:all"
        
        # Try cache first
        if use_cache:
            cached_data = metadata_cache.get(cache_key)
            if cached_data is not None:
                logger.info("Cache hit for all metadata")
                if isinstance(cached_data, list) and all(
                    isinstance(item, ApplicationMetadata) for item in cached_data
                ):
                    return cached_data
                # Normalize any stale raw-dict list.
                models = [MetadataService._to_model(m) for m in cached_data]
                metadata_cache.set(cache_key, models)
                return models
        
        # Fetch from database
        metadata_list = metadata_db.get_all_metadata()
        models = [MetadataService._to_model(m) for m in metadata_list]
        
        # Store in cache
        if use_cache:
            metadata_cache.set(cache_key, models)
            logger.info(f"Cached {len(models)} metadata records")
        
        return models
    
    @staticmethod
    def add_metadata(
        app_name: str,
        description: Optional[str] = None,
        environment: Optional[str] = None,
        team: Optional[str] = None,
        github: Optional[Dict[str, Any]] = None,
        argocd: Optional[Dict[str, Any]] = None,
        grafana: Optional[Dict[str, Any]] = None,
        cost: Optional[Dict[str, Any]] = None,
        tags: Optional[List[str]] = None,
        created_by: Optional[str] = None
    ) -> tuple[bool, Optional[str]]:
        """
        Add new application metadata with validation.
        
        Args:
            app_name: Application name
            description: Application description
            environment: Environment (production, staging, development)
            team: Team name
            github: GitHub metadata dict
            argocd: ArgoCD metadata dict
            grafana: Grafana metadata dict
            cost: Cost metadata dict
            tags: List of tags
            created_by: User who created this
            
        Returns:
            Tuple of (success: bool, error_message: Optional[str])
        """
        try:
            # Validate required fields
            MetadataValidator.validate_app_name(app_name)
            
            if environment:
                MetadataValidator.validate_environment(environment)
            
            if team:
                MetadataValidator.validate_team(team)
            
            # Build metadata object
            from app.metadata.models import (
                GitHubMetadata, ArgoCDMetadata, GrafanaMetadata, CostMetadata
            )
            
            github_meta = GitHubMetadata(**github) if github else GitHubMetadata()
            argocd_meta = ArgoCDMetadata(**argocd) if argocd else ArgoCDMetadata()
            grafana_meta = GrafanaMetadata(**grafana) if grafana else GrafanaMetadata()
            cost_meta = CostMetadata(**cost) if cost else CostMetadata()
            
            # Validate integration metadata
            if github:
                MetadataValidator.validate_github_metadata(github_meta.enabled, github)
            
            if argocd:
                MetadataValidator.validate_argocd_metadata(argocd_meta.enabled, argocd)
            
            if grafana:
                MetadataValidator.validate_grafana_metadata(grafana_meta.enabled, grafana)
            
            if cost:
                MetadataValidator.validate_cost_metadata(cost_meta.enabled, cost)
            
            # Create metadata object
            metadata = ApplicationMetadata(
                app_name=app_name,
                description=description,
                environment=environment,
                team=team,
                github=github_meta,
                argocd=argocd_meta,
                grafana=grafana_meta,
                cost=cost_meta,
                created_by=created_by,
                updated_by=created_by,
                tags=tags
            )
            
            # Save to database (matches create_metadata(app_name, application_id, team, **kwargs))
            success = metadata_db.create_metadata(
                app_name=app_name,
                application_id=app_name,  # no separate app_id in this flow; use app_name as stable ID
                team=team or "",
                environment=environment,
                metadata_json=metadata.model_dump(exclude_none=True),
            )
            
            if success:
                # Invalidate list cache
                metadata_cache.delete("metadata:all")
                logger.info(f"Added metadata for: {app_name}")
                return (True, None)
            else:
                return (False, f"Metadata for '{app_name}' already exists")
        
        except ValidationError as e:
            error_msg = f"Validation error: {str(e)}"
            logger.warning(error_msg)
            return (False, error_msg)
        except Exception as e:
            error_msg = f"Error adding metadata: {str(e)}"
            logger.error(error_msg)
            return (False, error_msg)
    
    @staticmethod
    def update_metadata(
        app_name: str,
        description: Optional[str] = None,
        environment: Optional[str] = None,
        team: Optional[str] = None,
        github: Optional[Dict[str, Any]] = None,
        argocd: Optional[Dict[str, Any]] = None,
        grafana: Optional[Dict[str, Any]] = None,
        cost: Optional[Dict[str, Any]] = None,
        tags: Optional[List[str]] = None,
        updated_by: Optional[str] = None
    ) -> tuple[bool, Optional[str]]:
        """
        Update existing metadata with validation.
        
        Args:
            app_name: Application name
            description: Updated description
            environment: Updated environment
            team: Updated team
            github: Updated GitHub metadata
            argocd: Updated ArgoCD metadata
            grafana: Updated Grafana metadata
            cost: Updated Cost metadata
            tags: Updated tags
            updated_by: User who performed update
            
        Returns:
            Tuple of (success: bool, error_message: Optional[str])
        """
        try:
            # Check if metadata exists
            existing = metadata_db.get_metadata(app_name)
            if not existing:
                error_msg = f"Metadata for '{app_name}' not found"
                logger.warning(error_msg)
                return (False, error_msg)
            
            # Validate updates
            if environment:
                MetadataValidator.validate_environment(environment)
            
            if team:
                MetadataValidator.validate_team(team)
            
            # Build update dict
            update_dict = {}
            
            if description is not None:
                update_dict["description"] = description
            
            if environment is not None:
                update_dict["environment"] = environment
            
            if team is not None:
                update_dict["team"] = team
            
            if tags is not None:
                update_dict["tags"] = tags
            
            # Handle integration updates
            if github is not None:
                from app.metadata.models import GitHubMetadata
                MetadataValidator.validate_github_metadata(
                    github.get("enabled", False), github
                )
                update_dict["github"] = GitHubMetadata(**github).dict()
            
            if argocd is not None:
                from app.metadata.models import ArgoCDMetadata
                MetadataValidator.validate_argocd_metadata(
                    argocd.get("enabled", False), argocd
                )
                update_dict["argocd"] = ArgoCDMetadata(**argocd).dict()
            
            if grafana is not None:
                from app.metadata.models import GrafanaMetadata
                MetadataValidator.validate_grafana_metadata(
                    grafana.get("enabled", False), grafana
                )
                update_dict["grafana"] = GrafanaMetadata(**grafana).dict()
            
            if cost is not None:
                from app.metadata.models import CostMetadata
                MetadataValidator.validate_cost_metadata(
                    cost.get("enabled", False), cost
                )
                update_dict["cost"] = CostMetadata(**cost).dict()
            
            # Update in database
            success = metadata_db.update_metadata(
                app_name, update_dict
            )
            
            if success:
                # Invalidate caches
                metadata_cache.delete(f"metadata:{app_name}")
                metadata_cache.delete("metadata:all")
                logger.info(f"Updated metadata for: {app_name}")
                return (True, None)
            else:
                return (False, f"Failed to update metadata for '{app_name}'")
        
        except ValidationError as e:
            error_msg = f"Validation error: {str(e)}"
            logger.warning(error_msg)
            return (False, error_msg)
        except Exception as e:
            error_msg = f"Error updating metadata: {str(e)}"
            logger.error(error_msg)
            return (False, error_msg)
    
    @staticmethod
    def delete_metadata(app_name: str) -> tuple[bool, Optional[str]]:
        """
        Delete metadata for an application.
        
        Args:
            app_name: Application name
            
        Returns:
            Tuple of (success: bool, error_message: Optional[str])
        """
        try:
            # Delete from database
            success = metadata_db.delete_metadata(app_name)
            
            if success:
                # Invalidate caches
                metadata_cache.delete(f"metadata:{app_name}")
                metadata_cache.delete("metadata:all")
                logger.info(f"Deleted metadata for: {app_name}")
                return (True, None)
            else:
                return (False, f"Metadata for '{app_name}' not found")
        
        except Exception as e:
            error_msg = f"Error deleting metadata: {str(e)}"
            logger.error(error_msg)
            return (False, error_msg)
    
    @staticmethod
    def search_metadata(query: str, use_cache: bool = False) -> List[ApplicationMetadata]:
        """
        Search metadata by query (not cached as results are dynamic).
        
        Args:
            query: Search query
            use_cache: Not used for search (always fresh results)
            
        Returns:
            List of matching ApplicationMetadata objects
        """
        try:
            results = metadata_db.search_metadata(query)
            models = [MetadataService._to_model(r) for r in results]
            logger.info(f"Search results for '{query}': {len(models)} matches")
            return models
        except Exception as e:
            logger.error(f"Error searching metadata: {e}")
            return []
    
    @staticmethod
    def get_configured_integrations(app_name: str) -> Dict[str, bool]:
        """
        Get enabled integrations for an application.
        
        Args:
            app_name: Application name
            
        Returns:
            Dictionary of integration names and enabled status
        """
        try:
            # Try to get from cache first
            metadata = MetadataService.get_metadata(app_name, use_cache=True)
            
            if not metadata:
                logger.warning(f"Metadata not found for: {app_name}")
                return {}
            
            integrations = {
                "github": metadata.github.enabled,
                "argocd": metadata.argocd.enabled,
                "grafana": metadata.grafana.enabled,
                "cost": metadata.cost.enabled
            }
            
            logger.info(f"Retrieved integrations for {app_name}: {integrations}")
            return integrations
        
        except Exception as e:
            logger.error(f"Error getting integrations for {app_name}: {e}")
            return {}
    
    @staticmethod
    def get_cache_stats() -> Dict[str, Any]:
        """
        Get cache statistics.
        
        Returns:
            Cache statistics dictionary
        """
        return metadata_cache.get_stats()
    
    @staticmethod
    def clear_cache(pattern: Optional[str] = None) -> int:
        """
        Clear cache entries.
        
        Args:
            pattern: Optional pattern to match (supports * wildcard). If None, clears all.
            
        Returns:
            Number of entries cleared
        """
        if pattern:
            count = metadata_cache.invalidate_pattern(pattern)
        else:
            metadata_cache.clear()
            count = metadata_cache.get_stats()["total_entries"]
        
        logger.info(f"Cache cleared: {count} entries")
        return count
