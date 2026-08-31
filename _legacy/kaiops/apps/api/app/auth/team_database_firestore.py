"""
Team Database with Firestore

Persistent storage for teams, assignments, and permissions.
"""
from typing import Dict, Optional, List
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeout
from ..database.firestore_config import FirestoreConfig
import uuid
import logging

logger = logging.getLogger(__name__)

class TeamDatabase:
    """Firestore-backed team database for RBAC."""
    
    def __init__(self):
        """Initialize team database."""
        try:
            self.db = FirestoreConfig.get_client()
            self.collection = self.db.collection("teams")
            self.users_collection = self.db.collection("users")
            self.agents_collection = self.db.collection("team_agents")
            logger.info("[OK] Team database initialized with Firestore")
            ex = ThreadPoolExecutor(max_workers=1)
            try:
                ex.submit(self._create_default_teams).result(timeout=12)
            except FuturesTimeout:
                logger.warning("[WARN] Default team seeding timed out — Firestore unreachable at startup")
            finally:
                ex.shutdown(wait=False)
        except Exception as e:
            logger.error(f"Failed to initialize team database: {e}")
            raise
    
    def _create_default_teams(self):
        """Create default teams."""
        try:
            teams_ref = self.collection.limit(1).get(timeout=8)
            if len(teams_ref) > 0:
                logger.info("Default teams already exist")
                return
            
            logger.info("Creating default teams...")
            now = datetime.now().isoformat()
            
            teams = [
                {
                    "id": str(uuid.uuid4()),
                    "name": "SRE Team",
                    "description": "Site Reliability Engineering team responsible for system monitoring and incident response",
                    "is_active": True,
                    "created_at": now,
                    "updated_at": now,
                    "members": []
                },
                {
                    "id": str(uuid.uuid4()),
                    "name": "DevOps Team",
                    "description": "Development Operations team managing CI/CD pipelines and deployments",
                    "is_active": True,
                    "created_at": now,
                    "updated_at": now,
                    "members": []
                },
                {
                    "id": str(uuid.uuid4()),
                    "name": "Security Team",
                    "description": "Information Security team handling security monitoring and compliance",
                    "is_active": True,
                    "created_at": now,
                    "updated_at": now,
                    "members": []
                }
            ]
            
            for team in teams:
                self.collection.document(team["id"]).set(team, timeout=8)

            logger.info("[OK] Default teams created successfully")
            
        except Exception as e:
            logger.error(f"[FAIL] Error creating default teams: {e}")
    
    def create_team(self, name: str, description: Optional[str] = None) -> Dict:
        """Create a new team."""
        try:
            team_id = str(uuid.uuid4())
            now = datetime.now().isoformat()
            
            team = {
                "id": team_id,
                "name": name,
                "description": description,
                "is_active": True,
                "created_at": now,
                "updated_at": now,
                "members": []
            }
            
            self.collection.document(team_id).set(team)
            logger.info(f"[OK] Created team: {name}")
            
            return {
                "id": team["id"],
                "name": team["name"],
                "description": team["description"],
                "is_active": team["is_active"],
                "created_at": team["created_at"],
                "updated_at": team["updated_at"]
            }
            
        except Exception as e:
            logger.error(f"[FAIL] Error creating team: {e}")
            raise
    
    def get_team(self, team_id: str) -> Optional[Dict]:
        """Get team by ID."""
        try:
            doc = self.collection.document(team_id).get()
            if doc.exists:
                data = doc.to_dict()
                return {
                    "id": data.get("id"),
                    "name": data.get("name"),
                    "description": data.get("description"),
                    "is_active": data.get("is_active"),
                    "created_at": data.get("created_at"),
                    "updated_at": data.get("updated_at")
                }
            return None
        except Exception as e:
            logger.error(f"Error getting team {team_id}: {e}")
            return None
    
    def get_all_teams(self) -> List[Dict]:
        """Get all teams."""
        try:
            docs = self.collection.where("is_active", "==", True).get()
            teams = []
            for doc in docs:
                data = doc.to_dict()
                teams.append({
                    "id": data.get("id"),
                    "name": data.get("name"),
                    "description": data.get("description"),
                    "is_active": data.get("is_active"),
                    "created_at": data.get("created_at"),
                    "updated_at": data.get("updated_at")
                })
            return teams
        except Exception as e:
            logger.error(f"Error getting all teams: {e}")
            return []
    
    def update_team(self, team_id: str, updates: Dict) -> Optional[Dict]:
        """Update team details."""
        try:
            doc = self.collection.document(team_id).get()
            if not doc.exists:
                logger.warning(f"Team {team_id} not found")
                return None
            
            allowed_fields = ['name', 'description', 'is_active']
            update_data = {}
            for key, value in updates.items():
                if key in allowed_fields:
                    update_data[key] = value
            
            if not update_data:
                return self.get_team(team_id)
                
            update_data["updated_at"] = datetime.now().isoformat()
            self.collection.document(team_id).update(update_data)
            
            logger.info(f"[OK] Updated team: {team_id}")
            return self.get_team(team_id)
            
        except Exception as e:
            logger.error(f"[FAIL] Error updating team: {e}")
            raise
    
    def delete_team(self, team_id: str) -> bool:
        """Delete a team."""
        try:
            doc = self.collection.document(team_id).get()
            if not doc.exists:
                logger.warning(f"Team {team_id} not found")
                return False
            
            self.collection.document(team_id).delete()
            logger.info(f"[OK] Deleted team: {team_id}")
            return True
            
        except Exception as e:
            logger.error(f"[FAIL] Error deleting team: {e}")
            return False
            
    def assign_user_to_team(
        self,
        user_id: str,
        team_id: str,
        is_team_lead: bool = False,
        assigned_by: Optional[str] = None
    ) -> Dict:
        """Assign a user to a team."""
        try:
            # Check user
            user_doc = self.users_collection.document(user_id).get()
            if not user_doc.exists:
                raise ValueError("User not found")
                
            # Check team
            team_ref = self.collection.document(team_id)
            team_doc = team_ref.get()
            if not team_doc.exists:
                raise ValueError("Team not found")
                
            data = team_doc.to_dict()
            members = data.get("members", [])
            
            # Check if already assigned
            for member in members:
                if member.get("user_id") == user_id:
                    logger.warning(f"User {user_id} already assigned to team {team_id}")
                    raise ValueError("User already assigned to this team")
            
            assignment = {
                "id": str(uuid.uuid4()),
                "user_id": user_id,
                "is_team_lead": is_team_lead,
                "assigned_at": datetime.now().isoformat(),
                "assigned_by": assigned_by or "system"
            }

            members.append(assignment)
            team_ref.update({"members": members, "updated_at": datetime.now().isoformat()})

            logger.info(f"[OK] Assigned user {user_id} to team {team_id}")
            return {
                "id": assignment["id"],
                "user_id": user_id,
                "team_id": team_id,
                "is_team_lead": is_team_lead,
                "assigned_at": assignment["assigned_at"],
                "assigned_by": assignment["assigned_by"]
            }

        except Exception as e:
            logger.error(f"[FAIL] Error assigning user to team: {e}")
            raise

    def get_team_members(self, team_id: str) -> List[Dict]:
        """Get all members of a team."""
        try:
            team_doc = self.collection.document(team_id).get()
            if not team_doc.exists:
                return []
                
            data = team_doc.to_dict()
            members_data = data.get("members", [])
            
            members = []
            for m in members_data:
                user_id = m.get("user_id")
                if not user_id:
                    continue
                user_doc = self.users_collection.document(user_id).get()
                if user_doc.exists:
                    u_data = user_doc.to_dict()
                    members.append({
                        "id": u_data.get("id"),
                        "username": u_data.get("username"),
                        "email": u_data.get("email"),
                        "full_name": u_data.get("full_name"),
                        "role": u_data.get("role"),
                        # Membership metadata sourced from the team doc's member sub-object
                        "user_id": user_id,
                        "is_team_lead": bool(m.get("is_team_lead", False)),
                        "assigned_at": m.get("assigned_at") or data.get("created_at", "")
                    })

            return members
            
        except Exception as e:
            logger.error(f"Error getting team members for {team_id}: {e}")
            return []

    def get_user_teams(self, user_id: str) -> List[Dict]:
        """Get all teams for a user."""
        try:
            docs = self.collection.get()
            teams = []
            for doc in docs:
                data = doc.to_dict()
                members = data.get("members", [])
                for m in members:
                    if m.get("user_id") == user_id:
                        teams.append({
                            "id": data.get("id"),
                            "name": data.get("name"),
                            "description": data.get("description"),
                            "is_active": data.get("is_active"),
                            "created_at": data.get("created_at"),
                            "updated_at": data.get("updated_at"),
                            "is_team_lead": bool(m.get("is_team_lead", False))
                        })
                        break
            return teams
            
        except Exception as e:
            logger.error(f"Error getting teams for user {user_id}: {e}")
            return []
            
    def remove_user_from_team(self, user_id: str, team_id: str) -> bool:
        """Remove a user from a team."""
        try:
            team_ref = self.collection.document(team_id)
            team_doc = team_ref.get()
            if not team_doc.exists:
                return False
                
            data = team_doc.to_dict()
            members = data.get("members", [])
            new_members = [m for m in members if m.get("user_id") != user_id]
            
            if len(members) != len(new_members):
                team_ref.update({"members": new_members})
                logger.info(f"[OK] Removed user {user_id} from team {team_id}")
                return True
                
            return False
            
        except Exception as e:
            logger.error(f"[FAIL] Error removing user from team: {e}")
            return False

    def update_team_lead(self, team_id: str, user_id: str, is_team_lead: bool) -> bool:
        """Set or clear the team lead flag on a team member."""
        try:
            team_ref = self.collection.document(team_id)
            team_doc = team_ref.get()
            if not team_doc.exists:
                logger.warning(f"Team {team_id} not found")
                return False

            data = team_doc.to_dict()
            members = data.get("members", [])

            found = False
            for member in members:
                if member.get("user_id") == user_id:
                    member["is_team_lead"] = is_team_lead
                    found = True
                    break

            if not found:
                logger.warning(f"User {user_id} is not a member of team {team_id}")
                return False

            team_ref.update({"members": members, "updated_at": datetime.now().isoformat()})
            logger.info(f"[OK] Set is_team_lead={is_team_lead} for user {user_id} on team {team_id}")
            return True

        except Exception as e:
            logger.error(f"[FAIL] Error updating team lead: {e}")
            return False

    # ==================== TEAM AGENT ASSIGNMENTS ====================

    @staticmethod
    def _enum_value(value) -> Optional[str]:
        """Coerce an enum member or plain string into its string value."""
        if value is None:
            return None
        return value.value if hasattr(value, "value") else str(value)

    def assign_team_agent(self, team_id: str, agent_type, priority, assigned_by: Optional[str] = None) -> Dict:
        """Assign an agent to a team with a priority."""
        try:
            team_doc = self.collection.document(team_id).get()
            if not team_doc.exists:
                raise ValueError("Team not found")

            agent_value = self._enum_value(agent_type)
            priority_value = self._enum_value(priority)

            # Reject duplicate assignments of the same agent to the same team
            existing = self.agents_collection.where("team_id", "==", team_id) \
                .where("agent_type", "==", agent_value).limit(1).get()
            if len(existing) > 0:
                raise ValueError("Agent already assigned to this team")

            assignment_id = str(uuid.uuid4())
            assignment = {
                "id": assignment_id,
                "team_id": team_id,
                "agent_type": agent_value,
                "priority": priority_value,
                "assigned_by": assigned_by or "system",
                "assigned_at": datetime.now().isoformat()
            }

            self.agents_collection.document(assignment_id).set(assignment)
            logger.info(f"[OK] Assigned agent {agent_value} to team {team_id}")
            return assignment

        except Exception as e:
            logger.error(f"[FAIL] Error assigning agent to team: {e}")
            raise

    def get_team_agents(self, team_id: str, priority: Optional[str] = None) -> List[Dict]:
        """Get all agent assignments for a team, optionally filtered by priority."""
        try:
            query = self.agents_collection.where("team_id", "==", team_id)
            if priority:
                query = query.where("priority", "==", self._enum_value(priority))

            agents = []
            for doc in query.get():
                data = doc.to_dict()
                agents.append({
                    "id": data.get("id"),
                    "team_id": data.get("team_id"),
                    "agent_type": data.get("agent_type"),
                    "priority": data.get("priority"),
                    "assigned_by": data.get("assigned_by") or "system",
                    "assigned_at": data.get("assigned_at")
                })

            agents.sort(key=lambda a: a.get("assigned_at") or "")
            return agents

        except Exception as e:
            logger.error(f"Error getting agents for team {team_id}: {e}")
            return []

    def remove_team_agent(self, agent_id: str) -> bool:
        """Remove an agent assignment by its assignment ID."""
        try:
            doc_ref = self.agents_collection.document(agent_id)
            if not doc_ref.get().exists:
                logger.warning(f"Agent assignment {agent_id} not found")
                return False

            doc_ref.delete()
            logger.info(f"[OK] Removed agent assignment: {agent_id}")
            return True

        except Exception as e:
            logger.error(f"[FAIL] Error removing agent assignment: {e}")
            return False

    def grant_permission(self, user_id: str, resource: str, action: str) -> Dict:
        """Grant a permission to a user."""
        try:
            perms_collection = self.db.collection("user_permissions")
            perm_id = str(uuid.uuid4())
            
            perm = {
                "id": perm_id,
                "user_id": user_id,
                "resource": resource,
                "action": action,
                "granted": True,
                "created_at": datetime.now().isoformat()
            }
            
            perms_collection.document(perm_id).set(perm)
            
            return {
                "id": perm_id,
                "user_id": user_id,
                "resource": resource,
                "action": action,
                "granted": True
            }
            
        except Exception as e:
            logger.error(f"[FAIL] Error granting permission: {e}")
            raise
            
    def get_user_permissions(self, user_id: str) -> List[Dict]:
        """Get all permissions for a user."""
        try:
            docs = self.db.collection("user_permissions").where("user_id", "==", user_id).get()
            result = []
            for doc in docs:
                data = doc.to_dict()
                result.append({
                    "id": data.get("id"),
                    "resource": data.get("resource"),
                    "action": data.get("action"),
                    "granted": data.get("granted")
                })
            return result
            
        except Exception as e:
            logger.error(f"Error getting permissions for user {user_id}: {e}")
            return []

# Global database instance
team_db = TeamDatabase()
