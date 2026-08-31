"""
Firestore Configuration

Centralized Firestore connection management for all SRE Agent data.
"""
import os
import logging
from typing import Optional
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeout
from google.cloud import firestore

logger = logging.getLogger(__name__)


class FirestoreConfig:
    """Firestore connection manager."""
    
    _client: Optional[firestore.Client] = None
    
    @classmethod
    def get_client(cls) -> firestore.Client:
        """Get or create Firestore client (singleton)."""
        if cls._client is None:
            try:
                # GOOGLE_CLOUD_PROJECT is the standard ADC env var; GOOGLE_PROJECT_ID is a fallback.
                project_id = os.getenv("GOOGLE_CLOUD_PROJECT") or os.getenv("GOOGLE_PROJECT_ID")
                if project_id:
                    cls._client = firestore.Client(project=project_id)
                else:
                    cls._client = firestore.Client()

                # Workaround for google-cloud-firestore>=2.20 double-encoding:
                # the lazy _database_string property encodes '(default)' as
                # '%28default%29' and transports URL-encode again, causing
                # "400 Invalid database id %28default%29". Pre-seed the cache
                # with the literal so transports encode exactly once.
                try:
                    db_id = os.getenv("FIRESTORE_DATABASE_ID", "(default)")
                    if db_id == "(default)" and hasattr(cls._client, "_database_string_internal"):
                        resolved_project = (
                            getattr(cls._client, "project", None)
                            or project_id
                            or ""
                        )
                        if resolved_project:
                            cls._client._database_string_internal = (
                                f"projects/{resolved_project}/databases/(default)"
                            )
                except Exception:
                    pass  # best-effort compatibility shim

                logger.info("[OK] Firestore client initialized successfully")
            except Exception as e:
                logger.error(f"Firestore client initialization failed: {e}")
                raise

        return cls._client

    @classmethod
    def check_database_exists(cls) -> bool:
        """Check if Firestore connection is working (max 10s to prevent startup hangs)."""
        def _probe():
            client = cls.get_client()
            next(client.collections(), None)

        ex = ThreadPoolExecutor(max_workers=1)
        try:
            ex.submit(_probe).result(timeout=10)
            return True
        except FuturesTimeout:
            logger.error("Firestore health check timed out (no ADC or network issue)")
            return False
        except Exception as e:
            logger.error(f"Firestore check failed: {e}")
            return False
        finally:
            ex.shutdown(wait=False)

# Collections
class Collections:
    USERS = "users"
    TEAMS = "teams"
    APPLICATIONS = "applications"
    APPLICATION_METADATA = "application_metadata"
    FEEDBACK = "feedback"
    TRAINING_DATASET = "training_dataset"
    EVALUATION_DATASET = "evaluation_dataset"
    USER_PERMISSIONS = "user_permissions"
    TEAM_PERMISSIONS = "team_permissions"

