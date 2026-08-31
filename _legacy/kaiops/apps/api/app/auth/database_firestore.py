"""
User Database with Firestore

Persistent storage for user authentication and profiles.
"""
from typing import Dict, Optional, List
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeout
from ..database.firestore_config import FirestoreConfig
from .models import UserRole
from .utils import get_password_hash
import uuid
import logging
import os

logger = logging.getLogger(__name__)

class UserDatabase:
    """Firestore-backed user database for authentication."""
    
    def __init__(self):
        """Initialize user database."""
        try:
            self.db = FirestoreConfig.get_client()
            self.collection = self.db.collection("users")
            logger.info("[OK] User database initialized with Firestore")
            ex = ThreadPoolExecutor(max_workers=1)
            try:
                ex.submit(self._create_default_users).result(timeout=12)
            except FuturesTimeout:
                logger.warning("[WARN] Default user seeding timed out — Firestore unreachable at startup")
            finally:
                ex.shutdown(wait=False)
        except Exception as e:
            logger.error(f"Failed to initialize user database: {e}")
            raise
    
    def _create_default_users(self):
        """Create default users only when SEED_DEMO_USERS=true (dev/demo environments)."""
        if os.getenv("SEED_DEMO_USERS", "false").lower() != "true":
            logger.info("Skipping default user seeding (SEED_DEMO_USERS != true)")
            return
        try:
            # Check if any users exist (short timeout so a bad ADC doesn't hang startup)
            users_ref = self.collection.limit(1).get(timeout=8)
            if len(users_ref) > 0:
                logger.info("Default users already exist")
                return
            
            logger.info("Creating default users...")
            now = datetime.now().isoformat()
            
            # Default admin user
            admin_user = {
                "id": "admin",
                "username": "admin",
                "email": "admin@example.com",
                "password_hash": get_password_hash("admin123"),
                "full_name": "System Administrator",
                "role": UserRole.ADMIN,
                "is_active": True,
                "created_at": now,
                "updated_at": now
            }
            
            # Default regular user
            user_user = {
                "id": "user",
                "username": "user",
                "email": "user@example.com",
                "password_hash": get_password_hash("user123"),
                "full_name": "Demo User",
                "role": UserRole.USER,
                "is_active": True,
                "created_at": now,
                "updated_at": now
            }
            
            # Default team lead user
            teamlead_user = {
                "id": str(uuid.uuid4()),
                "username": "teamlead",
                "email": "teamlead@example.com",
                "password_hash": get_password_hash("teamlead123"),
                "full_name": "Team Lead User",
                "role": UserRole.TEAM_LEAD,
                "is_active": True,
                "created_at": now,
                "updated_at": now
            }
            
            self.collection.document(admin_user["id"]).set(admin_user, timeout=8)
            self.collection.document(user_user["id"]).set(user_user, timeout=8)
            self.collection.document(teamlead_user["id"]).set(teamlead_user, timeout=8)
            
            logger.info("[OK] Default users created successfully")
            
        except Exception as e:
            logger.error(f"[FAIL] Error creating default users: {e}")
    
    def create_user(self, username: str, email: str, password: str, full_name: Optional[str] = None, role: str = "user") -> Dict:
        """Create a new user."""
        try:
            # Check if user already exists
            if self.get_user(username):
                logger.warning(f"User {username} already exists")
                raise ValueError(f"User {username} already exists")
            
            if self.get_user_by_email(email):
                logger.warning(f"Email {email} already in use")
                raise ValueError(f"Email {email} already in use")
            
            user_id = str(uuid.uuid4())
            now = datetime.now().isoformat()
            
            user = {
                "id": user_id,
                "username": username,
                "email": email,
                "password_hash": get_password_hash(password),
                "full_name": full_name,
                "role": role,
                "is_active": True,
                "created_at": now,
                "updated_at": now
            }
            
            self.collection.document(user_id).set(user)
            logger.info(f"[OK] Created user: {username}")
            return user
            
        except Exception as e:
            logger.error(f"[FAIL] Error creating user: {e}")
            raise
    
    def get_user(self, username: str) -> Optional[Dict]:
        """Get user by username."""
        try:
            docs = self.collection.where("username", "==", username).limit(1).get()
            for doc in docs:
                return doc.to_dict()
            return None
        except Exception as e:
            logger.error(f"Error getting user {username}: {e}")
            return None
    
    def get_user_by_id(self, user_id: str) -> Optional[Dict]:
        """Get user by ID."""
        try:
            doc = self.collection.document(user_id).get()
            if doc.exists:
                return doc.to_dict()
            return None
        except Exception as e:
            logger.error(f"Error getting user {user_id}: {e}")
            return None
    
    def get_user_by_email(self, email: str) -> Optional[Dict]:
        """Get user by email."""
        try:
            docs = self.collection.where("email", "==", email).limit(1).get()
            for doc in docs:
                return doc.to_dict()
            return None
        except Exception as e:
            logger.error(f"Error getting user by email {email}: {e}")
            return None
    
    def get_all_users(self, skip: int = 0, limit: int = 100) -> List[Dict]:
        """Get all users with pagination."""
        try:
            # Firestore limit and offset
            docs = self.collection.limit(limit).offset(skip).get()
            return [doc.to_dict() for doc in docs]
        except Exception as e:
            logger.error(f"Error getting all users: {e}")
            return []
    
    def get_users_by_role(self, role: str) -> List[Dict]:
        """Get all users with a specific role."""
        try:
            docs = self.collection.where("role", "==", role).get()
            return [doc.to_dict() for doc in docs]
        except Exception as e:
            logger.error(f"Error getting users by role {role}: {e}")
            return []
    
    def update_user(self, username: str, updates: Dict) -> Optional[Dict]:
        """Update user details."""
        try:
            user = self.get_user(username)
            if not user:
                logger.warning(f"User {username} not found")
                return None
            
            allowed_fields = ['full_name', 'email', 'role', 'is_active']
            update_data = {}
            for key, value in updates.items():
                if key in allowed_fields:
                    update_data[key] = value
            
            if not update_data:
                return user
                
            update_data["updated_at"] = datetime.now().isoformat()
            self.collection.document(user["id"]).update(update_data)
            
            # Fetch updated user
            updated_user = self.get_user(username)
            logger.info(f"[OK] Updated user: {username}")
            return updated_user
            
        except Exception as e:
            logger.error(f"[FAIL] Error updating user {username}: {e}")
            raise
    
    def change_password(self, username: str, new_password: str) -> bool:
        """Change user password."""
        try:
            user = self.get_user(username)
            if not user:
                logger.warning(f"User {username} not found")
                return False
            
            update_data = {
                "password_hash": get_password_hash(new_password),
                "updated_at": datetime.now().isoformat()
            }
            self.collection.document(user["id"]).update(update_data)
            
            logger.info(f"[OK] Changed password for user: {username}")
            return True
            
        except Exception as e:
            logger.error(f"[FAIL] Error changing password for user {username}: {e}")
            return False
    
    def delete_user(self, username: str) -> bool:
        """Delete a user."""
        try:
            user = self.get_user(username)
            if not user:
                logger.warning(f"User {username} not found")
                return False
            
            self.collection.document(user["id"]).delete()
            logger.info(f"[OK] Deleted user: {username}")
            return True
            
        except Exception as e:
            logger.error(f"[FAIL] Error deleting user {username}: {e}")
            return False

# Global database instance
user_db = UserDatabase()
