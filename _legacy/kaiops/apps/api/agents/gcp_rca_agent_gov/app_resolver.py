"""
GCP Application Resolver - Dynamically resolves application metadata to GKE deployment information.
"""
from typing import Optional, Dict, Any

class GCPAppResolver:
    _app_cache = {}
    
    @classmethod
    def get_app_metadata(cls, app_name: str) -> Optional[Dict[str, Any]]:
        cache_key = app_name.lower()
        if cache_key in cls._app_cache:
            return cls._app_cache[cache_key]
        
        try:
            from app.applications.database_firestore import application_db
            app = application_db.get_application_by_name(app_name)
            if app:
                app_dict = {
                    "id": app.get("id"),
                    "application_name": app.get("application_name"),
                    "cloud_provider": app.get("cloud_provider"),
                    "gke_cluster_name": app.get("gke_cluster_name"),
                    "namespace": app.get("namespace") or "default",
                    "gcp_project_id": app.get("gcp_project_id"),
                    "status": str(app.get("status")) if app.get("status") else None,
                    "application_owner": app.get("application_owner"),
                    "argocd_app_name": app.get("argocd_app_name")
                }
                cls._app_cache[cache_key] = app_dict
                return app_dict
            return None
        except Exception as e:
            print(f"Error fetching app metadata for '{app_name}': {e}")
            return None
    
    @classmethod
    def resolve_pod_info(cls, app_name: str) -> Dict[str, Any]:
        meta = cls.get_app_metadata(app_name)
        if not meta:
            return {"error": f"Application '{app_name}' not found"}
        
        dep_name = meta.get("argocd_app_name") or meta.get("application_name")
        return {
            "application_name": meta.get("application_name"),
            "namespace": meta.get("namespace", "default"),
            "gke_cluster": meta.get("gke_cluster_name"),
            "is_multi_deployment": False,
            "deployments": [
                {
                    "deployment_name": dep_name,
                    "pod_name": dep_name,
                    "namespace": meta.get("namespace", "default"),
                    "criticality": "high"
                }
            ]
        }

def get_pod_info(app_name: str) -> Dict[str, Any]:
    return GCPAppResolver.resolve_pod_info(app_name)

def get_ingress_info(app_name: str) -> Dict[str, Any]:
    meta = GCPAppResolver.get_app_metadata(app_name)
    if not meta:
        return {"error": f"Application '{app_name}' not found"}
    return {
        "application_name": meta.get("application_name"),
        "namespace": meta.get("namespace", "default"),
        "ingress_name": meta.get("argocd_app_name") or meta.get("application_name")
    }
