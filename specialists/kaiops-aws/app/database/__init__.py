"""
Database initialization module.
Replaced PostgreSQL with Google Cloud Firestore backend.
"""

from .firestore_config import FirestoreConfig

__all__ = ["FirestoreConfig"]
