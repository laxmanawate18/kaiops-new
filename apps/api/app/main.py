import os
import sys
import asyncio
import warnings
import uvicorn
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from google.adk.cli.fast_api import get_fast_api_app


from dotenv import load_dotenv
load_dotenv()
from app.auth.routes import router as auth_router
from app.auth.team_routes import router as team_router
from app.feedback.routes import router as feedback_router
from app.chat.routes import router as chat_router
from app.applications.routes import router as applications_router
from app.metadata.routes import router as metadata_router
from app.runtime.routes import router as runtime_router
from app.slack.interactions import router as slack_router

# Load environment variables from .env file
from dotenv import load_dotenv
load_dotenv()

# Import new middleware and utilities (non-breaking additions)
from app.middleware import RequestContextMiddleware
from app.cache import get_cache_manager
import logging
from urllib.parse import quote

# Configure structured logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Suppress only known harmless warnings from ADK/GenAI internals
warnings.filterwarnings("ignore", category=RuntimeWarning, message=".*async.*generator.*")
warnings.filterwarnings("ignore", category=UserWarning, message=".*EXPERIMENTAL.*")
warnings.filterwarnings("ignore", category=UserWarning, message=".*non-text parts in the response.*")

# Configuration
AGENT_DIR = os.path.abspath(os.path.join(os.path.dirname(os.path.dirname(__file__)), "agents"))

# Use Vertex AI Session Service for ADK or default memory
SESSION_DB_URL = "vertexai://" if os.getenv("USE_VERTEX_SESSIONS") == "true" else None

# CORS allowed origins - allow all origins in local and production
raw_origins = os.getenv("ALLOWED_ORIGINS", "*")
if raw_origins == "*":
    ALLOWED_ORIGINS = ["*"]
else:
    ALLOWED_ORIGINS = [orig.strip() for orig in raw_origins.split(",") if orig.strip()]


# Global variables to store app state
app_state = {}

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for startup and shutdown events."""
    
    # Startup
    logger.info("=" * 70)
    logger.info("Starting ADK FastAPI application...")
    logger.info("=" * 70)
    
    # Initialize Firestore connection
    from app.database.firestore_config import FirestoreConfig
    try:
        if FirestoreConfig.check_database_exists():
            logger.info(f"[OK] Firestore database connected")
            app_state["firestore_connected"] = True
        else:
            logger.error(f" Failed to connect to Firestore: Database health check failed")
            logger.error("Database connection failed. Continuing in degraded mode.")
            app_state["firestore_connected"] = False
    except Exception as e:
        logger.error(f" Failed to connect to Firestore: {e}")
        logger.error("Database connection failed. Continuing in degraded mode.")
        app_state["firestore_connected"] = False
    
    # Log new features
    logger.info("[OK] Features enabled:")
    logger.info("  • Custom exception hierarchy with error context")
    logger.info("  • Request correlation IDs for tracing")
    logger.info("  • Multi-layer caching (Redis + in-memory)")
    logger.info("  • Integration health checks")
    logger.info("  • Audit logging for operations")
    logger.info("  • Structured response models")
    logger.info("  • Timeout management for operations")
    
    app_state["agents_loaded"] = True
    logger.info(f"Agent directory: {AGENT_DIR}")
    if os.getenv("SEED_DEMO_USERS", "false").lower() == "true":
        logger.info("Default users seeded: admin, teamlead, user")  # passwords never logged
    else:
        logger.info("Default user seeding skipped (SEED_DEMO_USERS != true)")
    logger.info("Default teams: SRE Team, DevOps Team, Security Team")
    logger.info("[OK] All systems initialized")
    logger.info("=" * 70)
    
    yield
    
    # Shutdown  
    logger.info("Shutting down ADK FastAPI application...")
    try:
        app_state.clear()
        logger.info("[OK] Shutdown completed successfully")
    except Exception as e:
        logger.error(f"Error during shutdown: {e}", exc_info=True)

def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    
    # Create ADK FastAPI app
    adk_app = get_fast_api_app(
        agents_dir=AGENT_DIR,
        session_service_uri=SESSION_DB_URL,
        allow_origins=ALLOWED_ORIGINS,
        web=False,  # Disable ADK web interface to avoid conflicts - we use custom routes instead
        lifespan=lifespan
    )
    
    # Add request context middleware (for correlation IDs and request tracking)
    adk_app.add_middleware(RequestContextMiddleware)

    # Require JWT auth on ADK agent routes (/list-apps, /run, /run_sse, /apps/*).
    # Added BEFORE CORS below: add_middleware is LIFO (last added = outermost),
    # so CORS stays outermost for preflight handling. This middleware passes
    # OPTIONS through, so preflights are unaffected.
    from app.middleware import ADKAuthMiddleware
    adk_app.add_middleware(ADKAuthMiddleware)

    # Rate-limit auth endpoints (/api/v1/auth/login, /register, /refresh,
    # /password) per client IP to blunt credential-stuffing and brute force.
    from app.middleware import AuthRateLimitMiddleware
    adk_app.add_middleware(AuthRateLimitMiddleware)

    # Strip ADK's eval-set debugger routes. They annotate pydantic models with
    # mcp.client.session.ClientSession, which breaks OpenAPI schema generation
    # (GET /openapi.json -> 500). KaiOps does not use ADK evals.
    from fastapi.routing import APIRoute
    adk_app.router.routes = [
        r for r in adk_app.router.routes
        if not (isinstance(r, APIRoute) and "/eval" in getattr(r, "path", ""))
    ]
    
    # Add CORS middleware with regex to permit all origins dynamically
    adk_app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"] if "*" in ALLOWED_ORIGINS else ALLOWED_ORIGINS,
        allow_origin_regex=".*" if "*" in ALLOWED_ORIGINS else None,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Honor X-Forwarded-* from Cloud Run so trailing-slash redirects keep the
    # https scheme instead of downgrading to http:// (mixed-content risk).
    from uvicorn.middleware.proxy_headers import ProxyHeadersMiddleware
    adk_app.add_middleware(ProxyHeadersMiddleware, trusted_hosts="*")
    
    # Initialize cache manager
    try:
        cache_manager = get_cache_manager()
        logger.info(f"[OK] Cache manager initialized: {cache_manager.get_stats()}")
    except Exception as e:
        logger.warning(f"[WARN] Cache manager initialization failed: {e}, continuing with defaults")
    
    # Include authentication routes
    adk_app.include_router(
        auth_router,
        prefix="/api/v1/auth",
        tags=["Authentication"]
    )
    
    # Include team management routes
    adk_app.include_router(
        team_router,
        prefix="/api/v1/teams",
        tags=["Team Management"]
    )
    
    # Include feedback routes - FIXED PREFIX
    adk_app.include_router(
        feedback_router,
        prefix="/api/v1/feedback",
        tags=["Feedback System"]
    )
    
    # Include chat session routes
    adk_app.include_router(
        chat_router,
        prefix="/api/v1/chat",
        tags=["Chat Sessions"]
    )
    
    # Include application registration routes
    adk_app.include_router(
        applications_router,
        prefix="/api/v1/applications",
        tags=["Application Registration"]
    )
    
    # Include metadata management routes
    adk_app.include_router(
        metadata_router,
        tags=["Metadata Management"]
    )
    
    # Include Agent Runtime routes (Autonomous Loop / Model C)
    adk_app.include_router(
        runtime_router,
        tags=["Agent Runtime"]
    )
    
    # Include Slack interactive actions (Approve/Reject HITL via Slack buttons)
    adk_app.include_router(
        slack_router,
        tags=["Slack Interactions"]
    )
    
    
    # Add a root endpoint
    @adk_app.get("/")
    async def root():
        return {
            "message": "ADK FastAPI Application with Team Management, Feedback System & Authentication",
            "version": "1.0.0", 
            "docs_url": "/docs",
            "authentication": {
                "login": "/api/v1/auth/login",
                "register": "/api/v1/auth/register",
                "me": "/api/v1/auth/me"
            },
            "team_management": {
                "teams": "/api/v1/teams/teams",
                "permissions": "/api/v1/teams/permissions",
                "stats": "/api/v1/teams/stats"
            },
            "feedback_system": {
                "create_feedback": "/api/v1/feedback",
                "my_feedback": "/api/v1/feedback/my",
                "review_pending": "/api/v1/feedback/pending",
                "stats": "/api/v1/feedback/stats",
                "datasets": "/api/v1/feedback/datasets/entries"
            },
            "chat_sessions": {
                "create_session": "/api/v1/chat/sessions",
                "get_sessions": "/api/v1/chat/sessions",
                "send_message": "/api/v1/chat/messages",
                "get_messages": "/api/v1/chat/sessions/{session_id}/messages",
                "stats": "/api/v1/chat/stats"
            },
            "applications": {
                "list": "/api/v1/applications/",
                "create": "/api/v1/applications/",
                "get": "/api/v1/applications/{app_id}",
                "update": "/api/v1/applications/{app_id}",
                "delete": "/api/v1/applications/{app_id}",
                "toggle_status": "/api/v1/applications/{app_id}/toggle",
                "search": "/api/v1/applications/search/query",
                "stats": "/api/v1/applications/stats/summary"
            },
            "adk_endpoints": {
                "list_agents": "/list-apps",
                "run_agent": "/run", 
                "run_agent_streaming": "/run_sse"
            },
            "custom_endpoints": {
                "health": "/api/v1/health",
                "chat": "/api/v1/chat",
                "stats": "/api/v1/stats"
            }
        }
    
    # Add health check endpoint
    @adk_app.get("/api/v1/health")
    async def health_check():
        """Health check endpoint for the entire API."""
        firestore_ok = app_state.get("firestore_connected", False)
        return {
            "status": "healthy" if firestore_ok else "degraded",
            "service": "sre_agent_api",
            "message": "API is running",
            "database": "firestore" if firestore_ok else "firestore (disconnected)",
            "firestore_connected": firestore_ok,
        }
    
    return adk_app

# Create the app instance
app = create_app()

if __name__ == "__main__":
    try:
        uvicorn.run(
            "app.main:app",
            host="0.0.0.0",
            port=8000,
            reload=True,
            log_level="info"
        )
    except KeyboardInterrupt:
        print("\nServer stopped gracefully")
        sys.exit(0)
    except Exception as e:
        print(f"\nServer error: {e}")
        sys.exit(1)
