# Graph Report - kaiops_latest  (2026-08-27)

## Corpus Check
- cluster-only mode — file stats not available

## Summary
- 1877 nodes · 3041 edges · 134 communities (106 shown, 28 thin omitted)
- Extraction: 94% EXTRACTED · 6% INFERRED · 0% AMBIGUOUS · INFERRED: 187 edges (avg confidence: 0.92)
- Token cost: 0 input · 0 output

## Community Hubs (Navigation)
- feedback/routes.py
- RequestContext
- MetadataValidator
- call_mcp_tool
- azure_rca_agent/tools.py
- aws_rca_agent/tools.py
- MetadataService
- api/app/auth/team_routes.py
- Any
- devDependencies
- azure-server/aks_mcp_server.py
- ApplicationDatabase
- VertexFirestoreSessionService
- models/__init__.py
- dependencies
- api/app/chat/agent_service.py
- FastAPI
- TeamDatabase
- applications/routes.py
- MetadataCache
- api/app/metadata/schemas.py
- web/src/components/ui/Dialog.tsx
- gcp_rca_agent/tools.py
- AuditLogger
- argocd-server/argocd_mcp_server.py
- web/src/App.tsx
- api/.venv-win/Scripts/pywin32_postinstall.py
- web/src/components/layout/AppShell.tsx
- approve_action_endpoint
- build_application_response
- sre_agent/agent.py
- FirestoreConfig
- ApplicationCreate
- auth/routes.py
- compilerOptions
- UserDatabase
- UserResponse
- chat/models.py
- MetadataDatabase
- grafana-server/grafana_mcp_server.py
- argocd_agent/tools.py
- aws_mcp_server.py
- github-server/github_mcp_server.py
- github_agent/tools.py
- async_timeout
- web/src/components/three/HeroParticles.tsx
- compilerOptions
- timedelta
- ui/primitives.tsx
- GCPConfig
- search_runbooks
- api/app/auth/dependencies.py
- web/src/components/chat/MessageBubble.tsx
- web/src/components/ui/Badge.tsx
- compilerOptions
- GrafanaMCPServer
- get_pending
- web/src/components/three/ServiceTopology.tsx
- web/src/components/ui/Input.tsx
- get_pod_info
- api/app/auth/token_blacklist.py
- restart_pod_real
- UserCreate
- delete_team
- web/src/components/login/HeroCore.tsx
- web/src/pages/LoginPage.tsx
- web/src/pages/ServicesPage.tsx
- scripts
- charts/primitives.tsx
- create-secrets.sh script
- get_all_users
- api/.venv-win/Scripts/pywin32_testall.py
- web/package.json
- web/src/components/layout/ProtectedRoute.tsx
- web/src/pages/AdminPage.tsx
- web/src/pages/ConsolePage.tsx
- web/src/pages/ProfilePage.tsx
- web/src/pages/RegisterPage.tsx
- web/src/pages/ServiceFormPage.tsx
- api/app/constants/http_status.py
- web/src/pages/ServiceDetailPage.tsx
- k8s/deploy-gke.sh
- delete_application
- delete_user
- web/src/components/chat/Composer.tsx
- web/src/components/chat/FeedbackDialog.tsx
- web/src/components/chat/SessionList.tsx
- web/src/components/ui/CountUp.tsx
- web/src/stores/ui.ts
- web/src/vite-env.d.ts
- web/tsconfig.json
- k8s/deploy-backend-agent.sh
- k8s/deploy-frontend-cloudrun.sh
- argocd_agent/prompt.py
- github_agent/prompt.py
- grafana_agent/prompt.py
- metadata_agent/prompt.py
- sre_agent/prompt.py
- chat/__init__.py
- metadata/__init__.py
- web/docker-entrypoint.sh
- axios
- deps/package.json
- k8s/setup-gke.sh
- k8s/update-api-url.sh
- azure-server/__init__.py

## God Nodes (most connected - your core abstractions)
1. `UserResponse` - 78 edges
2. `call_mcp_tool()` - 25 edges
3. `ApplicationDatabase` - 24 edges
4. `VertexFirestoreSessionService` - 24 edges
5. `RequestContext` - 22 edges
6. `FeedbackDatabase` - 21 edges
7. `MetadataService` - 21 edges
8. `TeamDatabase` - 20 edges
9. `MetadataValidator` - 19 edges
10. `ValidationError` - 19 edges

## Surprising Connections (you probably didn't know these)
- `ApplicationDatabase` --uses--> `ApplicationStats`  [INFERRED]
  apps/api/app/applications/database_firestore.py → apps/api/app/applications/models.py
- `ApplicationDatabase` --uses--> `ApplicationStatus`  [INFERRED]
  apps/api/app/applications/database_firestore.py → apps/api/app/applications/models.py
- `get_session_service()` --uses--> `VertexFirestoreSessionService`  [INFERRED]
  apps/api/app/chat/agent_service.py → apps/api/app/chat/custom_session_service.py
- `VertexFirestoreSessionService` --uses--> `FirestoreConfig`  [INFERRED]
  apps/api/app/chat/custom_session_service.py → apps/api/app/database/firestore_config.py
- `get_applications_by_status()` --uses--> `ApplicationStatus`  [INFERRED]
  apps/api/app/applications/routes.py → apps/api/app/applications/models.py

## Import Cycles
- None detected.

## Communities (134 total, 28 thin omitted)

### Community 0 - "feedback/routes.py"
Cohesion: 0.05
Nodes (55): FeedbackDatabase, Feedback Database with Firestore Persistent storage for AI feedback and…, Get feedback by user., Get all pending feedback for review., Get feedback by status., Update feedback status., Review feedback and update status., Firestore-backed feedback database for AI response improvement. (+47 more)

### Community 1 - "RequestContext"
Cohesion: 0.05
Nodes (45): AuthenticationError, AuthorizationError, BadRequestError, ConflictError, CredentialsError, DatabaseError, DuplicateResourceError, InsufficientRoleError (+37 more)

### Community 2 - "MetadataValidator"
Cohesion: 0.07
Nodes (40): ApplicationMetadata, ArgoCDMetadata, Config, CostMetadata, GitHubMetadata, GrafanaMetadata, BaseModel, Pydantic models for application metadata storage. Defines data structures for… (+32 more)

### Community 3 - "call_mcp_tool"
Cohesion: 0.06
Nodes (49): Grafana Agent Domain expert for observability and system monitoring.…, _call_and_format_grafana_mcp(), get_dashboard_summary(), list_alert_rules(), Grafana Agent Tools Tool functions for observability and monitoring via Grafana…, Helper to call MCP and return the raw text content., Search for Grafana dashboards by query with comprehensive details., Get detailed summary of a Grafana dashboard by UID. (+41 more)

### Community 4 - "azure_rca_agent/tools.py"
Cohesion: 0.08
Nodes (45): get_current_iso_time(), Azure RCA Agent - LlmAgent with Official Azure Monitor MCP Tools This module…, Returns current UTC time in ISO 8601 format for timestamping., AppResolver, get_ingress_info(), get_pod_info(), Any, Azure Application Resolver - Dynamically resolves application metadata to AKS… (+37 more)

### Community 5 - "aws_rca_agent/tools.py"
Cohesion: 0.08
Nodes (35): get_current_iso_time(), AWS RCA Agent - Google ADK Agent for CloudWatch-based RCA This module…, Returns the current Coordinated Universal Time (UTC) date and time in the ISO…, AWSAppResolver, get_ingress_info(), get_pod_info(), Any, AWS Application Resolver - Dynamically resolves application metadata to EKS… (+27 more)

### Community 6 - "MetadataService"
Cohesion: 0.07
Nodes (36): get_current_admin_user(), Get current user if they are an admin., create_metadata(), delete_metadata(), get_configured_integrations(), get_metadata(), list_metadata(), delete (+28 more)

### Community 7 - "api/app/auth/team_routes.py"
Cohesion: 0.08
Nodes (41): AgentStats, AgentType, BaseModel, Stats for a specific agent, Overall system statistics, Model for assigning an agent to a team, Response model for team agent assignments, SystemStats (+33 more)

### Community 8 - "Any"
Cohesion: 0.08
Nodes (24): Get GCP service account credentials. Returns:…, Get the GCP project ID., GCPLoadBalancerClient, GCPLoggingClient, GCPMonitoringClient, Any, GCP Cloud Logging & Monitoring Client - Execute real queries against GCP APIs…, Execute Cloud Logging Insights query. Args: query: Cloud Logging query string… (+16 more)

### Community 9 - "devDependencies"
Cohesion: 0.05
Nodes (40): devDependencies, autoprefixer, eslint, @eslint/js, eslint-plugin-react-hooks, eslint-plugin-react-refresh, globals, postcss (+32 more)

### Community 10 - "azure-server/aks_mcp_server.py"
Cohesion: 0.08
Nodes (38): JSONResponse, _get_ingress_logs(), _get_pod_describe(), _get_pod_events(), _get_pod_logs(), handle_call_tool(), handle_list_tools(), _list_pods() (+30 more)

### Community 11 - "ApplicationDatabase"
Cohesion: 0.06
Nodes (17): ApplicationDatabase, Create a new application, persisting every field supplied by the caller., Get application by ID., Get application by name (case-insensitive approximation)., Firestore-backed database for managing SRE-enabled applications., Get all applications with optional filtering and pagination., Initialize application database., List applications with optional filtering and pagination. (+9 more)

### Community 12 - "VertexFirestoreSessionService"
Cohesion: 0.09
Nodes (16): _normalize_record(), Any, Convert Firestore DatetimeWithNanoseconds/datetime values to ISO strings., Creates a session (sync version for API)., Normalize timestamp fields of a Firestore document dict to ISO strings., Custom ADK Session Service that persists memory states to Google Cloud…, Neutralize a consumed HITL gate message so UI refetches can never re-render it…, _to_iso() (+8 more)

### Community 13 - "models/__init__.py"
Cohesion: 0.11
Nodes (34): Data models and schemas for the application., AgentRunRequest, CustomChatRequest, CustomChatResponse, HealthResponse, Message, MessagePart, BaseModel (+26 more)

### Community 14 - "dependencies"
Cohesion: 0.05
Nodes (37): dependencies, clsx, cmdk, date-fns, framer-motion, @hookform/resolvers, lucide-react, @radix-ui/react-avatar (+29 more)

### Community 15 - "api/app/chat/agent_service.py"
Cohesion: 0.09
Nodes (32): SRE Agent Package Root orchestration layer for Site Reliability Engineering…, _build_user_content(), _dedupe_repeated_sections(), _ensure_adk_session(), _extract_confirmations(), _get_rtc(), Any, Agent service for handling AI agent calls in chat. This service integrates with… (+24 more)

### Community 16 - "FastAPI"
Cohesion: 0.08
Nodes (23): cache_key(), cached(), CacheManager, get_cache_manager(), Any, Caching manager with multi-layer caching strategy. Features: - L1 cache: In-…, Invalidate single cache entry., Invalidate multiple entries by pattern (e.g., 'metadata:*'). (+15 more)

### Community 17 - "TeamDatabase"
Cohesion: 0.07
Nodes (15): Firestore-backed team database for RBAC., Initialize team database., Assign a user to a team., Get all members of a team., Get all teams for a user., Remove a user from a team., Set or clear the team lead flag on a team member., Coerce an enum member or plain string into its string value. (+7 more)

### Community 18 - "applications/routes.py"
Cohesion: 0.14
Nodes (25): Application Database with Firestore Persistent storage for SRE-enabled…, Application Registration Module for SRE Agent., ApplicationHealthCheck, ApplicationListResponse, ApplicationResponse, ApplicationSearchQuery, ApplicationStats, ApplicationStatus (+17 more)

### Community 19 - "MetadataCache"
Cohesion: 0.09
Nodes (17): CacheEntry, MetadataCache, Any, Cache management for metadata with TTL support. Provides thread-safe in-memory…, Clear all cache entries., Invalidate all cache entries matching a pattern. Args: pattern: Key pattern to…, Get cache statistics., Represents a single cache entry with TTL. (+9 more)

### Community 20 - "api/app/metadata/schemas.py"
Cohesion: 0.12
Nodes (27): ArgoCDMetadataRequest, ArgoCDMetadataResponse, Config, ConfiguredIntegrationsResponse, CostMetadataRequest, CostMetadataResponse, CreateMetadataRequest, ErrorResponse (+19 more)

### Community 21 - "web/src/components/ui/Dialog.tsx"
Cohesion: 0.08
Nodes (19): Button, ButtonProps, Size, SIZES, Variant, VARIANTS, ConfirmDialogProps, ConfirmTone (+11 more)

### Community 22 - "gcp_rca_agent/tools.py"
Cohesion: 0.13
Nodes (19): get_current_iso_time(), GCP RCA Agent - Google ADK Agent for Cloud Logging-based RCA This module…, Returns the current Coordinated Universal Time (UTC) date and time in the ISO…, Get the GKE cluster name., GCP RCA Agent - Cloud Logging & Root Cause Analysis for GKE This agent performs…, _call_mcp_tool(), GCPLoadBalancerClient, GCPLoggingClient (+11 more)

### Community 23 - "AuditLogger"
Cohesion: 0.08
Nodes (13): AuditLogger, Any, Audit logging for sensitive operations. Tracks all changes to applications,…, Log permission denied attempts., Log all sensitive operations for compliance and debugging., Log integration connection., Log integration disconnection., Log data export for compliance. (+5 more)

### Community 24 - "argocd-server/argocd_mcp_server.py"
Cohesion: 0.10
Nodes (24): ArgocdMCPServer, get_application_details(), get_application_status(), get_deployment_history(), get_server_info(), list_applications(), list_projects(), list_repositories() (+16 more)

### Community 25 - "web/src/App.tsx"
Cohesion: 0.08
Nodes (12): AdminPage, App(), DashboardPage, FeedbackPage, LoginPage, NotFoundPage, ProfilePage, RegisterPage (+4 more)

### Community 26 - "api/.venv-win/Scripts/pywin32_postinstall.py"
Cohesion: 0.18
Nodes (20): CopyTo(), create_shortcut(), fixup_dbi(), get_root_hkey(), get_shortcuts_folder(), get_special_folder_path(), get_system_dir(), install() (+12 more)

### Community 27 - "web/src/components/layout/AppShell.tsx"
Cohesion: 0.10
Nodes (12): AmbientField, AppShell(), ROUTE_ACCENTS, routeAccent(), AmbientField, CAPABILITIES, CommandPalette(), NAV (+4 more)

### Community 28 - "approve_action_endpoint"
Cohesion: 0.14
Nodes (23): Restart a pod by deleting it (its controller recreates it). DESTRUCTIVE:…, restart_pod(), process_message(), Process a user message through the SRE agent using ADK's runner pattern. Args:…, ChatMessage, Config, Individual chat message model., Response when sending a message. (+15 more)

### Community 29 - "build_application_response"
Cohesion: 0.11
Nodes (23): build_application_response(), create_application(), get_application(), get_application_stats(), get_applications_by_cluster(), get_applications_by_owner(), get_applications_by_status(), get (+15 more)

### Community 30 - "sre_agent/agent.py"
Cohesion: 0.14
Nodes (19): Agent, Metadata Agent Domain expert for application metadata and context management.…, get_application_db(), list_all_applications(), query_mongodb(), Metadata Agent Tools Firestore tools for application metadata and configuration…, search_application_by_name(), analyze_pod_logs() (+11 more)

### Community 31 - "FirestoreConfig"
Cohesion: 0.12
Nodes (18): Search previous investigation sessions for similar past incidents and their…, Search expert-approved (APPROVED status) feedback for validated guidance on…, search_approved_feedback_tool(), search_past_incidents_tool(), _get_db(), Search past incidents and approved feedback for similar issues., Count how many query terms (>2 chars) appear in the text., Search previous investigation sessions for messages similar to the query.… (+10 more)

### Community 32 - "ApplicationCreate"
Cohesion: 0.13
Nodes (12): ApplicationCreate, ApplicationUpdate, validator, Validate namespace only if GCP provider is selected., Validate Azure Subscription ID only if Azure provider is selected., Validate AWS Account ID only if AWS provider is selected., Model for updating an existing application., Model for creating a new application with cloud-provider support. (+4 more)

### Community 33 - "auth/routes.py"
Cohesion: 0.17
Nodes (18): User Database with Firestore Persistent storage for user authentication and…, PasswordChange, Enum, RefreshTokenRequest, UserLogin, UserRole, UserUpdate, change_password() (+10 more)

### Community 34 - "compilerOptions"
Cohesion: 0.09
Nodes (21): compilerOptions, allowImportingTsExtensions, baseUrl, exactOptionalPropertyTypes, isolatedModules, jsx, lib, module (+13 more)

### Community 35 - "UserDatabase"
Cohesion: 0.13
Nodes (10): Get user by username., Get all users with pagination., Get all users with a specific role., Firestore-backed user database for authentication., Change user password., Initialize user database., Create default users only when SEED_DEMO_USERS=true (dev/demo environments)., UserDatabase (+2 more)

### Community 36 - "UserResponse"
Cohesion: 0.25
Nodes (20): UserResponse, get_session_service(), ChatSession, ChatStatsResponse, Chat statistics response., chat_health_check(), clear_messages(), create_session() (+12 more)

### Community 37 - "chat/models.py"
Cohesion: 0.13
Nodes (20): CreateSessionRequest, CreateSessionResponse, DeleteSessionResponse, GetMessagesResponse, GetSessionsResponse, MessageSender, BaseModel, Enum (+12 more)

### Community 38 - "MetadataDatabase"
Cohesion: 0.12
Nodes (12): MetadataDatabase, Any, Get metadata filtered by environment (dev, staging, prod)., Update metadata for an application., Delete metadata for an application., Firestore database operations for application metadata., Search metadata by application name or team., Initialize metadata database. (+4 more)

### Community 39 - "grafana-server/grafana_mcp_server.py"
Cohesion: 0.13
Nodes (17): get_dashboard_summary(), GrafanaMCPServer, list_alert_rules(), list_datasources(), Any, tool, query_loki(), query_prometheus() (+9 more)

### Community 40 - "argocd_agent/tools.py"
Cohesion: 0.16
Nodes (18): ArgoCD Agent Domain expert for deployment management and continuous delivery…, _call_and_format_argocd_mcp(), get_application_status(), get_deployment_history(), list_projects(), list_repositories(), ArgoCD Agent Tools Tool functions for deployment management via ArgoCD MCP…, Helper to call MCP and return the raw text content. (+10 more)

### Community 41 - "aws_mcp_server.py"
Cohesion: 0.16
Nodes (19): execute_log_insights(), _extract_method(), _extract_path(), get_alb_logs(), get_cloudwatch_metrics(), _get_cw_client(), get_log_events(), _get_logs_client() (+11 more)

### Community 42 - "github-server/github_mcp_server.py"
Cohesion: 0.13
Nodes (16): get_latest_commit(), get_repository_info(), get_user_repositories(), GitHubMCPServer, list_issues(), Any, tool, Get detailed information about a specific repository. (+8 more)

### Community 43 - "github_agent/tools.py"
Cohesion: 0.18
Nodes (16): GitHub Agent Domain expert for source code management and repository…, _call_and_format_github_mcp(), get_latest_commit(), get_repository_info(), get_user_repositories(), list_issues(), GitHub Agent Tools Tool functions for source code management via GitHub MCP…, Helper to call MCP and return the raw text content. (+8 more)

### Community 44 - "async_timeout"
Cohesion: 0.12
Nodes (10): Utility modules for common operations., async_timeout, Any, Timeout utilities for operations and external service calls. Prevents…, Context manager for asyncio.wait_for (Python 3.10 compatible)., Manage timeouts for various operations., Execute coroutine with timeout. Usage: result = await…, Decorator for async functions with timeout. Usage:… (+2 more)

### Community 45 - "web/src/components/three/HeroParticles.tsx"
Cohesion: 0.15
Nodes (11): AmbientField(), AmbientFieldProps, CanvasBoundary, isWebGLAvailable(), Props, State, buildLogoPositions(), HeroParticles() (+3 more)

### Community 46 - "compilerOptions"
Cohesion: 0.11
Nodes (17): compilerOptions, declaration, declarationMap, esModuleInterop, forceConsistentCasingInFileNames, module, moduleResolution, outDir (+9 more)

### Community 47 - "timedelta"
Cohesion: 0.18
Nodes (17): Token, login(), logout(), post, Revoke the presented access token (logout)., Authenticate user and return access token., Exchange a valid refresh token for a new access + refresh token pair., refresh() (+9 more)

### Community 48 - "ui/primitives.tsx"
Cohesion: 0.12
Nodes (7): Separator, Switch, Tabs, TabsContent, TabsList, TabsTrigger, TooltipProvider

### Community 49 - "GCPConfig"
Cohesion: 0.15
Nodes (9): GCPConfig, Any, GCP RCA Agent Configuration - Load GCP credentials and defaults from .env…, Get the GKE cluster zone., Get all GCP configuration as dictionary., Check if GCP is properly configured., GCP Configuration loader from environment variables., Validate GCP configuration. Returns: Tuple of (is_valid: bool, error_message:… (+1 more)

### Community 50 - "search_runbooks"
Cohesion: 0.20
Nodes (14): Search enterprise SRE runbooks and post-mortem documentation for incident…, search_runbooks(), _best_section(), _fetch_document_body(), _get_token(), _parse_data_store(), project_id_from_path(), Real Vertex AI Search grounding for SRE runbooks. Searches an enterprise… (+6 more)

### Community 51 - "api/app/auth/dependencies.py"
Cohesion: 0.17
Nodes (13): get_current_user(), get_optional_current_user(), Get current authenticated user., Get current user if authenticated, None otherwise., Dependency to check if user's team has access to a specific agent., require_agent_access(), AgentPriority, str (+5 more)

### Community 52 - "web/src/components/chat/MessageBubble.tsx"
Cohesion: 0.18
Nodes (9): ApprovalCard(), Markdown, isErrorMessage(), MessageBubble(), MessageBubbleProps, LIVE_PHASES, ReasoningTimeline(), STATUS_ICON (+1 more)

### Community 53 - "web/src/components/ui/Badge.tsx"
Cohesion: 0.14
Nodes (9): BadgeProps, CLOUD_META, CloudProvider, ServiceStatus, Severity, SEVERITY_STYLES, STATUS_META, Tone (+1 more)

### Community 54 - "compilerOptions"
Cohesion: 0.14
Nodes (13): compilerOptions, allowSyntheticDefaultImports, isolatedModules, lib, module, moduleDetection, moduleResolution, noEmit (+5 more)

### Community 56 - "get_pending"
Cohesion: 0.25
Nodes (10): consume_pending(), get_pending(), _purge_expired_locked(), Any, Server-side registry of actions awaiting human approval. An action is stored…, Remove expired records. Caller must hold _lock., Return the pending record for a valid, unexpired token, else None., Atomically remove and return the pending record (single-use). (+2 more)

### Community 57 - "web/src/components/three/ServiceTopology.tsx"
Cohesion: 0.25
Nodes (6): completenessOf(), NodeDatum, Provider, PROVIDER_COLOR, PROVIDER_ORDER, Scene()

### Community 58 - "web/src/components/ui/Input.tsx"
Cohesion: 0.25
Nodes (7): FieldProps, Input, InputProps, Textarea, TextareaProps, TextField, TextFieldProps

### Community 59 - "get_pod_info"
Cohesion: 0.46
Nodes (5): GCPAppResolver, get_ingress_info(), get_pod_info(), Any, GCP Application Resolver - Dynamically resolves application metadata to GKE…

### Community 60 - "api/app/auth/token_blacklist.py"
Cohesion: 0.32
Nodes (7): _cleanup(), is_revoked(), In-memory JWT blacklist for logout/revocation. Tokens are stored until their…, Add a token ID to the blacklist until its natural expiry., Check whether a token ID has been revoked., Drop expired entries. Must be called while holding _lock., revoke()

### Community 61 - "restart_pod_real"
Cohesion: 0.38
Nodes (6): _load_api(), _load_gke_api(), Real Kubernetes remediation executor. Credential resolution order for…, Delete a pod so its Deployment/StatefulSet recreates it (the standard…, Build an API client against GKE using ambient google.auth creds., restart_pod_real()

### Community 62 - "UserCreate"
Cohesion: 0.33
Nodes (3): validator, TeamCreate, UserCreate

### Community 63 - "delete_team"
Cohesion: 0.29
Nodes (7): delete_team(), delete, Delete a team (admin only)., Remove a user from a team (admin only)., Remove an agent assignment from a team (admin only)., remove_team_agent(), remove_user_from_team()

### Community 64 - "web/src/components/login/HeroCore.tsx"
Cohesion: 0.33
Nodes (6): BLIP_ANGLES, BLIP_DELAYS, HeroCore(), PROVIDERS, TICKER_POOL, useHexSize()

### Community 65 - "web/src/pages/LoginPage.tsx"
Cohesion: 0.29
Nodes (3): FormValues, HeroParticles, schema

### Community 66 - "web/src/pages/ServicesPage.tsx"
Cohesion: 0.29
Nodes (3): ServiceTopology, View, VIEWS

### Community 67 - "scripts"
Cohesion: 0.33
Nodes (6): scripts, build, dev, lint, preview, typecheck

### Community 69 - "create-secrets.sh script"
Cohesion: 0.33
Nodes (3): create-secrets.sh script, deploy-cloud.sh script, deploy-with-cloudbuild.sh script

### Community 70 - "get_all_users"
Cohesion: 0.40
Nodes (5): get_all_users(), get_current_user_info(), get, Get current user information., Get all users (admin only) with team information.

### Community 72 - "api/.venv-win/Scripts/pywin32_testall.py"
Cohesion: 0.60
Nodes (4): find_and_run(), main(), A test runner for pywin32, run_test()

### Community 73 - "web/package.json"
Cohesion: 0.40
Nodes (4): name, private, type, version

### Community 78 - "web/src/pages/ProfilePage.tsx"
Cohesion: 0.40
Nodes (3): passwordSchema, PasswordValues, ROLE_META

### Community 79 - "web/src/pages/RegisterPage.tsx"
Cohesion: 0.40
Nodes (3): FormValues, RULES, schema

### Community 80 - "web/src/pages/ServiceFormPage.tsx"
Cohesion: 0.40
Nodes (3): base, FormValues, schema

### Community 81 - "api/app/constants/http_status.py"
Cohesion: 0.50
Nodes (3): HTTPStatus, HTTP status code constants for consistent response status codes. Usage:…, Standardized HTTP status codes for all endpoints.

### Community 84 - "k8s/deploy-gke.sh"
Cohesion: 0.83
Nodes (3): check_status(), print_section(), deploy-gke.sh script

### Community 85 - "delete_application"
Cohesion: 0.67
Nodes (3): delete_application(), delete, Delete an application. Requires: Admin role only

### Community 86 - "delete_user"
Cohesion: 0.67
Nodes (3): delete_user(), delete, Delete a user (admin only).

## Knowledge Gaps
- **232 isolated node(s):** `ButtonProps`, `Size`, `Variant`, `ConfirmDialogProps`, `ConfirmTone` (+227 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **28 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `UserResponse` connect `UserResponse` to `feedback/routes.py`, `auth/routes.py`, `MetadataService`, `api/app/auth/team_routes.py`, `get_all_users`, `timedelta`, `applications/routes.py`, `api/app/auth/dependencies.py`, `delete_application`, `delete_user`, `approve_action_endpoint`, `build_application_response`, `delete_team`?**
  _High betweenness centrality (0.117) - this node is a cross-community bridge._
- **Why does `RequestContextMiddleware` connect `RequestContext` to `FastAPI`?**
  _High betweenness centrality (0.069) - this node is a cross-community bridge._
- **Why does `FirestoreConfig` connect `FirestoreConfig` to `feedback/routes.py`, `auth/routes.py`, `VertexFirestoreSessionService`, `FastAPI`, `applications/routes.py`, `api/app/auth/dependencies.py`?**
  _High betweenness centrality (0.069) - this node is a cross-community bridge._
- **Are the 26 inferred relationships involving `UserResponse` (e.g. with `get_current_admin_or_team_lead()` and `get_current_admin_user()`) actually correct?**
  _`UserResponse` has 26 INFERRED edges - model-reasoned connections that need verification._
- **Are the 2 inferred relationships involving `ApplicationDatabase` (e.g. with `ApplicationStats` and `ApplicationStatus`) actually correct?**
  _`ApplicationDatabase` has 2 INFERRED edges - model-reasoned connections that need verification._
- **Are the 2 inferred relationships involving `VertexFirestoreSessionService` (e.g. with `get_session_service()` and `FirestoreConfig`) actually correct?**
  _`VertexFirestoreSessionService` has 2 INFERRED edges - model-reasoned connections that need verification._
- **What connects `ButtonProps`, `Size`, `Variant` to the rest of the system?**
  _232 weakly-connected nodes found - possible documentation gaps or missing edges._