"""
Metadata Agent Tools

Firestore tools for application metadata and configuration management.
"""
import json
import os
import sys
from typing import Optional
from google.adk.tools import ToolContext
from cachetools import TTLCache

_query_cache = TTLCache(maxsize=50, ttl=120)

def get_application_db():
    try:
        from app.applications.database_firestore import application_db
        return application_db
    except Exception as e:
        print(f"Firestore ApplicationDatabase init failed: {e}")
        return None

async def search_application_by_name(app_name: str, tool_context: Optional[ToolContext] = None) -> str:
    try:
        db = get_application_db()
        if db is None:
            return "[FAIL] **Firestore Connection Failed**\nDatabase is unavailable. Please try again later."

        app = db.get_application_by_name(app_name)
        if not app:
            all_apps, total = db.list_applications(limit=50)
            if not all_apps:
                return f"[WARN] **Application Not Found**\nNo application named '{app_name}' exists. Database is empty."
            app_names = "\n".join([f"- {a.get('application_name')}" for a in all_apps if a.get('application_name')])
            return f"[WARN] **Application Not Found**\nNo application named '{app_name}' in database.\n\n**Available Applications:**\n{app_names}"

        response = f"**Application: {app.get('application_name')}**\n\n"
        response += f"- **Repository**: `{app.get('github_repo') or 'N/A'}`\n"
        response += f"- **Owner**: `{app.get('application_owner') or 'N/A'}`\n"
        response += f"- **Cluster**: `{app.get('gke_cluster_name') or 'N/A'}`\n"
        response += f"- **Namespace**: `{app.get('namespace') or 'N/A'}`\n"
        response += f"- **ArgoCD App**: `{app.get('argocd_app_name') or 'N/A'}`\n"
        response += f"- **Grafana Dashboard**: `{app.get('grafana_dashboard') or 'N/A'}`\n"
        dash_url = app.get("grafana_dashboard_url") or ""
        response += f"- **Grafana Dashboard URL**: `{dash_url or 'N/A'}`\n"
        alert_uid = app.get("grafana_alert") or ""
        response += f"- **Grafana Alert Rule**: `{alert_uid or 'N/A'}`\n"
        response += f"- **Cloud Provider**: `{app.get('cloud_provider') or 'N/A'}`\n"
        response += f"- **Description**: {app.get('description') or 'N/A'}\n"
        response += f"- **Status**: {app.get('status') or 'N/A'}\n"
        return response
    except Exception as e:
        return f"[FAIL] **Error Searching Application**: {str(e)}"

async def list_all_applications(tool_context: Optional[ToolContext] = None) -> str:
    try:
        db = get_application_db()
        if db is None:
            return "**[FAIL] Firestore Connection Failed** — database unavailable, please retry shortly."

        apps, total = db.list_applications(limit=100)
        if not apps:
            return "No applications are registered yet."

        stats = {"active": 0, "inactive": 0, "pending": 0}
        rows = []
        for app in apps:
            status = str(app.get("status", "unknown")).lower()
            if status in stats:
                stats[status] += 1
            rows.append({
                "name": app.get("application_name", "N/A"),
                "owner": app.get("application_owner", "N/A"),
                "cluster": app.get("gke_cluster_name") or "—",
                "provider": (app.get("cloud_provider") or "n/a").upper(),
                "status": status,
                "argocd": app.get("argocd_app_name", "N/A"),
                "repo": app.get("github_repo", ""),
            })

        def _emoji(s: str) -> str:
            return {"active": "🟢 active", "inactive": "🔴 inactive",
                    "pending": "🟡 pending"}.get(s, f"⚪ {s}")

        lines = [
            f"**Registered Applications** ({len(rows)} total — "
            f"🟢 {stats['active']} · 🔴 {stats['inactive']} · 🟡 {stats['pending']})",
            "",
            "| Application | Provider | Owner | Cluster | Status | ArgoCD | Repo |",
            "|---|---|---|---|---|---|---|",
        ]
        for r in rows:
            repo_link = f"[repo]({r['repo']})" if str(r["repo"]).startswith("http") else (r["repo"] or "—")
            lines.append(
                f"| {r['name']} | {r['provider']} | {r['owner']} | {r['cluster']} "
                f"| {_emoji(r['status'])} | {r['argocd']} | {repo_link} |"
            )
        lines.append("")
        lines.append("_Ask me to *investigate* any application by name for logs, deployment status or RCA._")
        return "\n".join(lines)
    except Exception as e:
        return f"[FAIL] **Error Listing Applications**: {str(e)}"
    except Exception as e:
        return json.dumps({
            "error": True,
            "message": "Error Listing Applications",
            "description": str(e),
            "applications": []
        })

async def query_mongodb(filter: dict, collection_name: Optional[str] = None, tool_context: Optional[ToolContext] = None) -> str:
    try:
        cache_key = f"applications:{json.dumps(filter, sort_keys=True, default=str)}"
        if cache_key in _query_cache:
            return _query_cache[cache_key]

        db = get_application_db()
        if db is None:
            return "Firestore not available. Please check database connection."

        app_name = filter.get("application_name")
        if app_name:
            if isinstance(app_name, dict) and "$regex" in app_name:
                apps = db.search_applications(app_name["$regex"])
            else:
                app = db.get_application_by_name(str(app_name))
                apps = [app] if app else []
        else:
            apps, total = db.list_applications(limit=100)

        result = json.dumps(apps, indent=2, default=str) if apps else "No matching documents found."
        _query_cache[cache_key] = result
        return result
    except Exception as e:
        return f"Firestore query error: {str(e)}"

__all__ = [
    "search_application_by_name",
    "list_all_applications",
    "query_mongodb"
]
