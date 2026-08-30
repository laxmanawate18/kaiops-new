# Graph Report - kaiops-new-version  (2026-08-27)

## Corpus Check
- cluster-only mode — file stats not available

## Summary
- 1918 nodes · 3079 edges · 174 communities (111 shown, 63 thin omitted)
- Extraction: 94% EXTRACTED · 6% INFERRED · 0% AMBIGUOUS · INFERRED: 182 edges (avg confidence: 0.92)
- Token cost: 0 input · 0 output

## ⚠️ Architectural Context & Errata (Manual Overrides)
*Read this section before planning structural refactors.*

1. **`mcp_proxy.py` is CRITICAL Production Code**: It is the HTTP JSON-RPC dispatcher used by all four Cloud Run MCP services (via `Dockerfile.mcp`). It is NOT dead code. Do not delete it. (The AST graph may incorrectly show it loosely coupled).
2. **RCA Tools are Intentionally Divergent**: The `analyze_pod_logs`, `check_application_logs`, etc. across AWS, Azure, and GCP agents share signatures but have entirely different engines (Azure = KQL, GCP = Cloud Logging, AWS = mock). **Do NOT merge them into a common tools file**, as this destroys the multi-cloud design.
3. **MCP Client Protocols Diverge**: The MCP clients (`call_mcp_tool`) for AWS, Azure, and generic use different underlying protocols (HTTP-MCP, mock, LA-REST). Do not attempt to unify them under a single base strategy class.
4. **`UserResponse` is a God Node by Design**: It is the central auth contract injected across the app. Do not attempt to extract or refactor it out of the `auth` module pre-demo, as it carries severe regression risk for near-zero functional gain.
5. **Feedback Module is Modularized**: The large 55-node "feedback" community is an artifact of AST clustering. The files are already correctly split into `database_firestore.py`, `routes.py`, and `models.py`. Do not attempt to split them further.

## Community Hubs (Navigation)
- feedback/routes.py
- RequestContext
- aws_rca_agent/tools.py
- call_mcp_tool
- aks_mcp_server.py
- models/__init__.py
- agent_service.py
- ApplicationDatabase
- UserResponse
- MetadataValidator
- TeamDatabase
- azure_rca_agent/tools.py
- MetadataCache
- Dialog.tsx
- schemas.py
- build_application_response
- AuditLogger
- .add_metadata
- MetadataService
- argocd_mcp_server.py
- auth/models.py
- App.tsx
- compilerOptions
- GCPMonitoringClient
- chat/models.py
- auth/routes.py
- pywin32_postinstall.py
- AppShell.tsx
- azure_rca_agent/mcp_client.py
- GCPConfig
- applications/routes.py
- sre_agent/agent.py
- VertexFirestoreSessionService
- ApplicationCreate
- devDependencies
- grafana_mcp_server.py
- compilerOptions
- approve_action_endpoint
- dependencies.py
- gcp_rca_agent/tools.py
- MetadataDatabase
- github_mcp_server.py
- HeroParticles.tsx
- compilerOptions
- chat/routes.py
- argocd_agent/tools.py
- github_agent/tools.py
- async_timeout
- ui/primitives.tsx
- UserDatabase
- .get_client
- FastAPI
- MessageBubble.tsx
- search_runbooks
- Badge.tsx
- .get_project_id
- create_metadata
- GrafanaMCPServer
- FirestoreConfig
- dependencies
- kaiops-web/package.json
- pending_actions.py
- axios
- devDependencies
- ServiceTopology.tsx
- Input.tsx
- restart_pod
- token_blacklist.py
- grafana-mcp-server/package.json
- Session
- LoginPage.tsx
- HeroCore.tsx
- ServicesPage.tsx
- update_user
- charts/primitives.tsx
- create-secrets.sh script
- get_current_user
- ProtectedRoute.tsx
- AdminPage.tsx
- ConsolePage.tsx
- ProfilePage.tsx
- RegisterPage.tsx
- ServiceFormPage.tsx
- dependencies
- get_all_users
- scripts
- pywin32_testall.py
- ServiceDetailPage.tsx
- deploy-gke.sh
- http_status.py
- Composer.tsx
- FeedbackDialog.tsx
- SessionList.tsx
- CountUp.tsx
- ui.ts
- vite-env.d.ts
- kaiops-web/tsconfig.json
- deploy-backend-agent.sh
- deploy-frontend-cloudrun.sh
- delete_application
- delete_user
- cmdk
- date-fns
- eslint-plugin-react-hooks
- eslint-plugin-react-refresh
- framer-motion
- globals
- docker-entrypoint.sh
- lucide-react
- @radix-ui/react-avatar
- @radix-ui/react-checkbox
- @radix-ui/react-dropdown-menu
- @radix-ui/react-label
- @radix-ui/react-popover
- @radix-ui/react-progress
- @radix-ui/react-scroll-area
- @radix-ui/react-select
- @radix-ui/react-separator
- @radix-ui/react-slot
- @radix-ui/react-switch
- @radix-ui/react-tabs
- @radix-ui/react-tooltip
- react
- react-dom
- react-hook-form
- react-markdown
- react-router-dom
- @react-three/fiber
- recharts
- rehype-highlight
- remark-gfm
- sonner
- tailwind-merge
- @tanstack/react-query
- zod
- zustand
- tailwindcss
- @types/react
- setup-gke.sh
- update-api-url.sh
- argocd_agent/prompt.py
- github_agent/prompt.py
- grafana_agent/prompt.py
- metadata_agent/prompt.py
- sre_agent/prompt.py
- chat/__init__.py
- metadata/__init__.py
- azure-mcp-server/__init__.py

## God Nodes (most connected - your core abstractions)
1. `UserResponse` - 78 edges
2. `call_mcp_tool()` - 28 edges
3. `VertexFirestoreSessionService` - 24 edges
4. `ApplicationDatabase` - 24 edges
5. `RequestContext` - 22 edges
6. `FeedbackDatabase` - 21 edges
7. `MetadataService` - 21 edges
8. `parse_mcp_response()` - 21 edges
9. `TeamDatabase` - 20 edges
10. `MetadataValidator` - 19 edges

## Surprising Connections (you probably didn't know these)
- `create_metadata()` --uses--> `CreateMetadataRequest`  [INFERRED]
  sre-agent-backend/app/metadata/routes.py → sre-agent-backend/app/metadata/schemas.py
- `update_metadata()` --uses--> `UpdateMetadataRequest`  [INFERRED]
  sre-agent-backend/app/metadata/routes.py → sre-agent-backend/app/metadata/schemas.py
- `create_metadata()` --uses--> `MetadataService`  [INFERRED]
  sre-agent-backend/app/metadata/routes.py → sre-agent-backend/app/metadata/service.py
- `delete_metadata()` --uses--> `MetadataService`  [INFERRED]
  sre-agent-backend/app/metadata/routes.py → sre-agent-backend/app/metadata/service.py
- `update_metadata()` --uses--> `MetadataService`  [INFERRED]
  sre-agent-backend/app/metadata/routes.py → sre-agent-backend/app/metadata/service.py

## Import Cycles
- None detected.

## Communities (174 total, 63 thin omitted)

### Community 0 - "feedback/routes.py"
Cohesion: 0.05
Nodes (55): FeedbackDatabase, Feedback Database with Firestore Persistent storage for AI feedback and…, Get feedback by user., Get all pending feedback for review., Get feedback by status., Update feedback status., Review feedback and update status., Firestore-backed feedback database for AI response improvement. (+47 more)

### Community 1 - "RequestContext"
Cohesion: 0.05
Nodes (45): AuthenticationError, AuthorizationError, BadRequestError, ConflictError, CredentialsError, DatabaseError, DuplicateResourceError, InsufficientRoleError (+37 more)

### Community 2 - "aws_rca_agent/tools.py"
Cohesion: 0.06
Nodes (40): get_current_iso_time(), AWS RCA Agent - Google ADK Agent for CloudWatch-based RCA This module…, Returns the current Coordinated Universal Time (UTC) date and time in the ISO…, AWSAppResolver, get_ingress_info(), get_pod_info(), Any, AWS Application Resolver - Dynamically resolves application metadata to EKS… (+32 more)

### Community 3 - "call_mcp_tool"
Cohesion: 0.07
Nodes (49): Grafana Agent Domain expert for observability and system monitoring.…, _call_and_format_grafana_mcp(), get_dashboard_summary(), list_alert_rules(), Grafana Agent Tools Tool functions for observability and monitoring via Grafana…, Helper to call MCP and return the raw text content., Search for Grafana dashboards by query with comprehensive details., Get detailed summary of a Grafana dashboard by UID. (+41 more)

### Community 4 - "aks_mcp_server.py"
Cohesion: 0.08
Nodes (39): JSONResponse, Request, _get_ingress_logs(), _get_pod_describe(), _get_pod_events(), _get_pod_logs(), handle_call_tool(), handle_list_tools() (+31 more)

### Community 5 - "models/__init__.py"
Cohesion: 0.11
Nodes (34): Data models and schemas for the application., AgentRunRequest, CustomChatRequest, CustomChatResponse, HealthResponse, Message, MessagePart, BaseModel (+26 more)

### Community 6 - "agent_service.py"
Cohesion: 0.09
Nodes (34): BaseException, Content, Runner, SRE Agent Package Root orchestration layer for Site Reliability Engineering…, _build_user_content(), _dedupe_repeated_sections(), _ensure_adk_session(), _extract_confirmations() (+26 more)

### Community 7 - "ApplicationDatabase"
Cohesion: 0.07
Nodes (16): ApplicationDatabase, Create a new application, persisting every field supplied by the caller., Get application by ID., Get application by name (case-insensitive approximation)., Firestore-backed database for managing SRE-enabled applications., Get all applications with optional filtering and pagination., List applications with optional filtering and pagination., Search applications by name or description. (+8 more)

### Community 8 - "UserResponse"
Cohesion: 0.11
Nodes (34): TeamResponse, UserResponse, assign_team_agent(), assign_user_to_team(), create_team(), delete_team(), get_agent_priorities(), get_all_teams() (+26 more)

### Community 9 - "MetadataValidator"
Cohesion: 0.10
Nodes (20): MetadataValidator, Any, Exception, Validation utilities for metadata fields and configurations. Provides…, Validate Kubernetes namespace (Kubernetes naming rules). Args: namespace:…, Validate Grafana dashboard ID. Args: dashboard_id: Dashboard ID Raises:…, Raised when metadata validation fails., Validate cost center name. Args: cost_center: Cost center name Raises:… (+12 more)

### Community 10 - "TeamDatabase"
Cohesion: 0.07
Nodes (15): Firestore-backed team database for RBAC., Initialize team database., Assign a user to a team., Get all members of a team., Get all teams for a user., Remove a user from a team., Set or clear the team lead flag on a team member., Coerce an enum member or plain string into its string value. (+7 more)

### Community 11 - "azure_rca_agent/tools.py"
Cohesion: 0.12
Nodes (23): get_current_iso_time(), Azure RCA Agent - LlmAgent with Official Azure Monitor MCP Tools This module…, Returns current UTC time in ISO 8601 format for timestamping., AppResolver, get_ingress_info(), get_pod_info(), Any, Azure Application Resolver - Dynamically resolves application metadata to AKS… (+15 more)

### Community 12 - "MetadataCache"
Cohesion: 0.09
Nodes (17): CacheEntry, MetadataCache, Any, Cache management for metadata with TTL support. Provides thread-safe in-memory…, Clear all cache entries., Invalidate all cache entries matching a pattern. Args: pattern: Key pattern to…, Get cache statistics., Represents a single cache entry with TTL. (+9 more)

### Community 13 - "Dialog.tsx"
Cohesion: 0.08
Nodes (19): Button, ButtonProps, Size, SIZES, Variant, VARIANTS, ConfirmDialogProps, ConfirmTone (+11 more)

### Community 14 - "schemas.py"
Cohesion: 0.12
Nodes (27): ArgoCDMetadataRequest, ArgoCDMetadataResponse, Config, ConfiguredIntegrationsResponse, CostMetadataRequest, CostMetadataResponse, CreateMetadataRequest, ErrorResponse (+19 more)

### Community 15 - "build_application_response"
Cohesion: 0.10
Nodes (27): build_application_response(), build_application_response_optimized(), create_application(), get_application(), get_application_stats(), get_applications_by_cluster(), get_applications_by_owner(), get_applications_by_status() (+19 more)

### Community 16 - "AuditLogger"
Cohesion: 0.08
Nodes (13): AuditLogger, Any, Audit logging for sensitive operations. Tracks all changes to applications,…, Log permission denied attempts., Log all sensitive operations for compliance and debugging., Log integration connection., Log integration disconnection., Log data export for compliance. (+5 more)

### Community 17 - ".add_metadata"
Cohesion: 0.14
Nodes (20): ApplicationMetadata, ArgoCDMetadata, Config, CostMetadata, GitHubMetadata, GrafanaMetadata, BaseModel, Pydantic models for application metadata storage. Defines data structures for… (+12 more)

### Community 18 - "MetadataService"
Cohesion: 0.12
Nodes (21): get_configured_integrations(), get_metadata(), list_metadata(), get, Admin API routes for metadata management. Provides REST endpoints for managing…, List all application metadata. Returns metadata for all registered applications…, Get metadata for a specific application. - **app_name**: Application name (path…, Search metadata by keyword. - **q**: Search query (required, minimum 1… (+13 more)

### Community 19 - "argocd_mcp_server.py"
Cohesion: 0.10
Nodes (24): ArgocdMCPServer, get_application_details(), get_application_status(), get_deployment_history(), get_server_info(), list_applications(), list_projects(), list_repositories() (+16 more)

### Community 20 - "auth/models.py"
Cohesion: 0.13
Nodes (21): AgentStats, PasswordChange, BaseModel, validator, Stats for a specific agent, Overall system statistics, Model for assigning an agent to a team, Response model for team agent assignments (+13 more)

### Community 21 - "App.tsx"
Cohesion: 0.08
Nodes (12): AdminPage, App(), DashboardPage, FeedbackPage, LoginPage, NotFoundPage, ProfilePage, RegisterPage (+4 more)

### Community 22 - "compilerOptions"
Cohesion: 0.08
Nodes (24): compilerOptions, allowImportingTsExtensions, baseUrl, exactOptionalPropertyTypes, isolatedModules, jsx, lib, module (+16 more)

### Community 23 - "GCPMonitoringClient"
Cohesion: 0.13
Nodes (15): GCPLoggingClient, GCPMonitoringClient, Any, Execute Cloud Logging Insights query. Args: query: Cloud Logging query string…, Return mock log data instantly (no API call)., Cloud Monitoring client for querying metrics., Get or create Cloud Monitoring client., Query Cloud Monitoring for pod CPU and Memory metrics. Args: pod_name: Pod name… (+7 more)

### Community 24 - "chat/models.py"
Cohesion: 0.11
Nodes (25): ChatStatsResponse, CreateSessionRequest, CreateSessionResponse, DeleteSessionResponse, GetMessagesResponse, GetSessionsResponse, MessageSender, BaseModel (+17 more)

### Community 25 - "auth/routes.py"
Cohesion: 0.16
Nodes (23): Token, change_password(), login(), logout(), post, Revoke the presented access token (logout)., Change user password., Authenticate user and return access token. (+15 more)

### Community 26 - "pywin32_postinstall.py"
Cohesion: 0.18
Nodes (20): CopyTo(), create_shortcut(), fixup_dbi(), get_root_hkey(), get_shortcuts_folder(), get_special_folder_path(), get_system_dir(), install() (+12 more)

### Community 27 - "AppShell.tsx"
Cohesion: 0.10
Nodes (12): AmbientField, AppShell(), ROUTE_ACCENTS, routeAccent(), AmbientField, CAPABILITIES, CommandPalette(), NAV (+4 more)

### Community 28 - "azure_rca_agent/mcp_client.py"
Cohesion: 0.21
Nodes (22): call_mcp_tool(), _discover_pods(), _fallback(), get_ingress_logs(), get_pod_description(), get_pod_events(), get_pod_logs(), _get_token() (+14 more)

### Community 29 - "GCPConfig"
Cohesion: 0.11
Nodes (14): get_current_iso_time(), GCP RCA Agent - Google ADK Agent for Cloud Logging-based RCA This module…, Returns the current Coordinated Universal Time (UTC) date and time in the ISO…, GCPConfig, Any, GCP RCA Agent Configuration - Load GCP credentials and defaults from .env…, Get the GKE cluster zone., Get all GCP configuration as dictionary. (+6 more)

### Community 30 - "applications/routes.py"
Cohesion: 0.18
Nodes (19): Application Database with Firestore Persistent storage for SRE-enabled…, Application Registration Module for SRE Agent., ApplicationHealthCheck, ApplicationListResponse, ApplicationResponse, ApplicationSearchQuery, ApplicationStats, ApplicationStatus (+11 more)

### Community 31 - "sre_agent/agent.py"
Cohesion: 0.14
Nodes (19): Agent, Metadata Agent Domain expert for application metadata and context management.…, get_application_db(), list_all_applications(), query_mongodb(), Metadata Agent Tools Firestore tools for application metadata and configuration…, search_application_by_name(), analyze_pod_logs() (+11 more)

### Community 32 - "VertexFirestoreSessionService"
Cohesion: 0.18
Nodes (9): BaseSessionService, _normalize_record(), Any, Convert Firestore DatetimeWithNanoseconds/datetime values to ISO strings., Creates a session (sync version for API)., Normalize timestamp fields of a Firestore document dict to ISO strings., Custom ADK Session Service that persists memory states to Google Cloud…, _to_iso() (+1 more)

### Community 33 - "ApplicationCreate"
Cohesion: 0.13
Nodes (12): ApplicationCreate, ApplicationUpdate, validator, Validate namespace only if GCP provider is selected., Validate Azure Subscription ID only if Azure provider is selected., Validate AWS Account ID only if AWS provider is selected., Model for updating an existing application., Model for creating a new application with cloud-provider support. (+4 more)

### Community 34 - "devDependencies"
Cohesion: 0.10
Nodes (21): autoprefixer, eslint, @eslint/js, devDependencies, autoprefixer, eslint, @eslint/js, postcss (+13 more)

### Community 35 - "grafana_mcp_server.py"
Cohesion: 0.13
Nodes (17): get_dashboard_summary(), GrafanaMCPServer, list_alert_rules(), list_datasources(), Any, tool, query_loki(), query_prometheus() (+9 more)

### Community 36 - "compilerOptions"
Cohesion: 0.10
Nodes (19): dist, node_modules, compilerOptions, declaration, declarationMap, esModuleInterop, forceConsistentCasingInFileNames, module (+11 more)

### Community 37 - "approve_action_endpoint"
Cohesion: 0.15
Nodes (20): Roll back an ArgoCD application to a specific commit or previous deployment.…, rollback_application(), ChatMessage, Config, Individual chat message model., get_pending(), Return the pending record for a valid, unexpired token, else None., add_message_to_session() (+12 more)

### Community 38 - "dependencies.py"
Cohesion: 0.17
Nodes (16): User Database with Firestore Persistent storage for user authentication and…, get_current_admin_or_team_lead(), get_current_admin_user(), Get current user if they are an admin., Get current user if they are an admin or team lead., Dependency to check if user's team has access to a specific agent., require_agent_access(), AgentPriority (+8 more)

### Community 39 - "gcp_rca_agent/tools.py"
Cohesion: 0.19
Nodes (14): GCPAppResolver, get_ingress_info(), get_pod_info(), Any, GCP Application Resolver - Dynamically resolves application metadata to GKE…, Get the GKE cluster name., analyze_pod_logs(), check_application_logs() (+6 more)

### Community 40 - "MetadataDatabase"
Cohesion: 0.14
Nodes (11): MetadataDatabase, Any, Get metadata filtered by environment (dev, staging, prod)., Update metadata for an application., Delete metadata for an application., Firestore database operations for application metadata., Search metadata by application name or team., Create metadata for an application. (+3 more)

### Community 41 - "github_mcp_server.py"
Cohesion: 0.13
Nodes (16): get_latest_commit(), get_repository_info(), get_user_repositories(), GitHubMCPServer, list_issues(), Any, tool, Get detailed information about a specific repository. (+8 more)

### Community 42 - "HeroParticles.tsx"
Cohesion: 0.15
Nodes (11): AmbientField(), AmbientFieldProps, CanvasBoundary, isWebGLAvailable(), Props, State, buildLogoPositions(), HeroParticles() (+3 more)

### Community 43 - "compilerOptions"
Cohesion: 0.11
Nodes (17): compilerOptions, allowSyntheticDefaultImports, isolatedModules, lib, module, moduleDetection, moduleResolution, noEmit (+9 more)

### Community 44 - "chat/routes.py"
Cohesion: 0.25
Nodes (17): patch, get_session_service(), ChatSession, chat_health_check(), clear_messages(), create_session(), delete_all_sessions(), delete_session() (+9 more)

### Community 45 - "argocd_agent/tools.py"
Cohesion: 0.18
Nodes (16): ArgoCD Agent Domain expert for deployment management and continuous delivery…, _call_and_format_argocd_mcp(), get_application_status(), get_deployment_history(), list_projects(), list_repositories(), ArgoCD Agent Tools Tool functions for deployment management via ArgoCD MCP…, Helper to call MCP and return the raw text content. (+8 more)

### Community 46 - "github_agent/tools.py"
Cohesion: 0.18
Nodes (16): GitHub Agent Domain expert for source code management and repository…, _call_and_format_github_mcp(), get_latest_commit(), get_repository_info(), get_user_repositories(), list_issues(), GitHub Agent Tools Tool functions for source code management via GitHub MCP…, Helper to call MCP and return the raw text content. (+8 more)

### Community 47 - "async_timeout"
Cohesion: 0.12
Nodes (10): Utility modules for common operations., async_timeout, Any, Timeout utilities for operations and external service calls. Prevents…, Context manager for asyncio.wait_for (Python 3.10 compatible)., Manage timeouts for various operations., Execute coroutine with timeout. Usage: result = await…, Decorator for async functions with timeout. Usage:… (+2 more)

### Community 48 - "ui/primitives.tsx"
Cohesion: 0.12
Nodes (7): Separator, Switch, Tabs, TabsContent, TabsList, TabsTrigger, TooltipProvider

### Community 49 - "UserDatabase"
Cohesion: 0.13
Nodes (8): Get user by username., Get all users with pagination., Get all users with a specific role., Firestore-backed user database for authentication., Change user password., Initialize user database., Create default users only when SEED_DEMO_USERS=true (dev/demo environments)., UserDatabase

### Community 50 - ".get_client"
Cohesion: 0.17
Nodes (6): Client, Initialize application database., Neutralize a consumed HITL gate message so UI refetches can never re-render it…, Get or create Firestore client (singleton)., Initialize feedback database., Initialize metadata database.

### Community 51 - "FastAPI"
Cohesion: 0.08
Nodes (23): FastAPI, cache_key(), cached(), CacheManager, get_cache_manager(), Any, Caching manager with multi-layer caching strategy. Features: - L1 cache: In-…, Invalidate single cache entry. (+15 more)

### Community 52 - "MessageBubble.tsx"
Cohesion: 0.18
Nodes (9): ApprovalCard(), Markdown, isErrorMessage(), MessageBubble(), MessageBubbleProps, LIVE_PHASES, ReasoningTimeline(), STATUS_ICON (+1 more)

### Community 53 - "search_runbooks"
Cohesion: 0.20
Nodes (14): Search enterprise SRE runbooks and post-mortem documentation for incident…, search_runbooks(), _best_section(), _fetch_document_body(), _get_token(), _parse_data_store(), project_id_from_path(), Real Vertex AI Search grounding for SRE runbooks. Searches an enterprise… (+6 more)

### Community 54 - "Badge.tsx"
Cohesion: 0.14
Nodes (9): BadgeProps, CLOUD_META, CloudProvider, ServiceStatus, Severity, SEVERITY_STYLES, STATUS_META, Tone (+1 more)

### Community 55 - ".get_project_id"
Cohesion: 0.18
Nodes (8): Get GCP service account credentials. Returns:…, Get the GCP project ID., GCPLoadBalancerClient, Get or create Cloud Logging client., Cloud Logging client for querying Load Balancer logs., Get Cloud Logging client., Query Cloud Logging for Cloud Load Balancer logs. Args: lines: Number of log…, Parse latency string to milliseconds.

### Community 56 - "create_metadata"
Cohesion: 0.16
Nodes (13): create_metadata(), delete_metadata(), delete, post, put, Update metadata for an existing application. - **app_name**: Application name…, Delete metadata for an application. - **app_name**: Application name (path…, Create new application metadata. - **app_name**: Unique application identifier… (+5 more)

### Community 58 - "FirestoreConfig"
Cohesion: 0.12
Nodes (18): Search previous investigation sessions for similar past incidents and their…, Search expert-approved (APPROVED status) feedback for validated guidance on…, search_approved_feedback_tool(), search_past_incidents_tool(), _get_db(), Search past incidents and approved feedback for similar issues., Count how many query terms (>2 chars) appear in the text., Search previous investigation sessions for messages similar to the query.… (+10 more)

### Community 59 - "dependencies"
Cohesion: 0.18
Nodes (11): clsx, @hookform/resolvers, dependencies, clsx, @hookform/resolvers, @radix-ui/react-dialog, @react-three/drei, three (+3 more)

### Community 60 - "kaiops-web/package.json"
Cohesion: 0.18
Nodes (10): name, private, scripts, build, dev, lint, preview, typecheck (+2 more)

### Community 61 - "pending_actions.py"
Cohesion: 0.28
Nodes (8): consume_pending(), _purge_expired_locked(), Any, Server-side registry of actions awaiting human approval. An action is stored…, Remove expired records. Caller must hold _lock., Atomically remove and return the pending record (single-use)., Cancel a pending action without executing anything., reject_pending()

### Community 64 - "devDependencies"
Cohesion: 0.22
Nodes (9): @types/node, typescript, @types/node, typescript, devDependencies, tsx, @types/node, typescript (+1 more)

### Community 65 - "ServiceTopology.tsx"
Cohesion: 0.25
Nodes (6): completenessOf(), NodeDatum, Provider, PROVIDER_COLOR, PROVIDER_ORDER, Scene()

### Community 66 - "Input.tsx"
Cohesion: 0.25
Nodes (7): FieldProps, Input, InputProps, Textarea, TextareaProps, TextField, TextFieldProps

### Community 67 - "restart_pod"
Cohesion: 0.28
Nodes (8): Restart a pod by deleting it (its controller recreates it). DESTRUCTIVE:…, restart_pod(), _load_api(), _load_gke_api(), Real Kubernetes remediation executor. Credential resolution order for…, Delete a pod so its Deployment/StatefulSet recreates it (the standard…, Build an API client against GKE using ambient google.auth creds., restart_pod_real()

### Community 68 - "token_blacklist.py"
Cohesion: 0.32
Nodes (7): _cleanup(), is_revoked(), In-memory JWT blacklist for logout/revocation. Tokens are stored until their…, Add a token ID to the blacklist until its natural expiry., Check whether a token ID has been revoked., Drop expired entries. Must be called while holding _lock., revoke()

### Community 70 - "grafana-mcp-server/package.json"
Cohesion: 0.25
Nodes (7): description, engines, node, main, name, type, version

### Community 71 - "Session"
Cohesion: 0.29
Nodes (3): Event, ListSessionsResponse, Session

### Community 72 - "LoginPage.tsx"
Cohesion: 0.29
Nodes (3): FormValues, HeroParticles, schema

### Community 73 - "HeroCore.tsx"
Cohesion: 0.33
Nodes (6): BLIP_ANGLES, BLIP_DELAYS, HeroCore(), PROVIDERS, TICKER_POOL, useHexSize()

### Community 74 - "ServicesPage.tsx"
Cohesion: 0.29
Nodes (3): ServiceTopology, View, VIEWS

### Community 75 - "update_user"
Cohesion: 0.29
Nodes (7): put, Update user role (admin only)., Toggle user active status (admin only)., Update user information (admin only)., toggle_user_active(), update_user(), update_user_role()

### Community 77 - "create-secrets.sh script"
Cohesion: 0.33
Nodes (3): create-secrets.sh script, deploy-cloud.sh script, deploy-with-cloudbuild.sh script

### Community 78 - "get_current_user"
Cohesion: 0.50
Nodes (5): HTTPAuthorizationCredentials, get_current_user(), get_optional_current_user(), Get current authenticated user., Get current user if authenticated, None otherwise.

### Community 83 - "ProfilePage.tsx"
Cohesion: 0.40
Nodes (3): passwordSchema, PasswordValues, ROLE_META

### Community 84 - "RegisterPage.tsx"
Cohesion: 0.40
Nodes (3): FormValues, RULES, schema

### Community 85 - "ServiceFormPage.tsx"
Cohesion: 0.40
Nodes (3): base, FormValues, schema

### Community 86 - "dependencies"
Cohesion: 0.40
Nodes (5): @modelcontextprotocol/sdk, dependencies, axios, @modelcontextprotocol/sdk, axios

### Community 87 - "get_all_users"
Cohesion: 0.40
Nodes (5): get_all_users(), get_current_user_info(), get, Get current user information., Get all users (admin only) with team information.

### Community 88 - "scripts"
Cohesion: 0.40
Nodes (5): scripts, build, clean, dev, start

### Community 90 - "pywin32_testall.py"
Cohesion: 0.60
Nodes (4): find_and_run(), main(), A test runner for pywin32, run_test()

### Community 93 - "deploy-gke.sh"
Cohesion: 0.83
Nodes (3): check_status(), print_section(), deploy-gke.sh script

### Community 94 - "http_status.py"
Cohesion: 0.50
Nodes (3): HTTPStatus, HTTP status code constants for consistent response status codes. Usage:…, Standardized HTTP status codes for all endpoints.

### Community 105 - "delete_application"
Cohesion: 0.67
Nodes (3): delete_application(), delete, Delete an application. Requires: Admin role only

### Community 106 - "delete_user"
Cohesion: 0.67
Nodes (3): delete_user(), delete, Delete a user (admin only).

## Knowledge Gaps
- **235 isolated node(s):** `UiState`, `ImportMeta`, `ImportMetaEnv`, `ButtonProps`, `Size` (+230 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **63 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `UserResponse` connect `UserResponse` to `feedback/routes.py`, `approve_action_endpoint`, `dependencies.py`, `delete_application`, `delete_user`, `update_user`, `chat/routes.py`, `get_current_user`, `build_application_response`, `MetadataService`, `auth/models.py`, `get_all_users`, `chat/models.py`, `auth/routes.py`, `applications/routes.py`?**
  _High betweenness centrality (0.100) - this node is a cross-community bridge._
- **Why does `FirestoreConfig` connect `FirestoreConfig` to `VertexFirestoreSessionService`, `feedback/routes.py`, `dependencies.py`, `.get_client`, `FastAPI`, `applications/routes.py`?**
  _High betweenness centrality (0.059) - this node is a cross-community bridge._
- **Why does `RequestContextMiddleware` connect `RequestContext` to `FastAPI`?**
  _High betweenness centrality (0.056) - this node is a cross-community bridge._
- **Are the 26 inferred relationships involving `UserResponse` (e.g. with `get_current_admin_or_team_lead()` and `get_current_admin_user()`) actually correct?**
  _`UserResponse` has 26 INFERRED edges - model-reasoned connections that need verification._
- **Are the 2 inferred relationships involving `VertexFirestoreSessionService` (e.g. with `get_session_service()` and `FirestoreConfig`) actually correct?**
  _`VertexFirestoreSessionService` has 2 INFERRED edges - model-reasoned connections that need verification._
- **Are the 2 inferred relationships involving `ApplicationDatabase` (e.g. with `ApplicationStats` and `ApplicationStatus`) actually correct?**
  _`ApplicationDatabase` has 2 INFERRED edges - model-reasoned connections that need verification._
- **What connects `UiState`, `ImportMeta`, `ImportMetaEnv` to the rest of the system?**
  _235 weakly-connected nodes found - possible documentation gaps or missing edges._