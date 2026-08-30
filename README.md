# KaiOps SRE Agent - Multi-Cloud Root Cause Analysis Platform

A comprehensive Site Reliability Engineering (SRE) agent system that provides intelligent root cause analysis (RCA) across multiple cloud providers (Azure, AWS, GCP) using AI-powered agents.

## 📋 Table of Contents

- [Overview](#overview)
- [Architecture](#architecture)
- [Project Structure](#project-structure)
- [Key Features](#key-features)
- [Technology Stack](#technology-stack)
- [Setup & Installation](#setup--installation)
- [Configuration](#configuration)
- [Running the Application](#running-the-application)
- [API Documentation](#api-documentation)
- [Multi-Cloud RCA System](#multi-cloud-rca-system)
- [Development](#development)
- [Troubleshooting](#troubleshooting)

---

## 🎯 Overview

**KaiOps SRE Agent** is an advanced automation platform that helps DevOps and SRE teams quickly identify and resolve infrastructure issues. It combines:

- **Multi-Cloud Support**: Azure, AWS, and GCP
- **Intelligent Analysis**: AI-powered RCA agents
- **Real-time Monitoring**: Logs, metrics, and deployment tracking
- **Modern UI**: React-based dashboard with WebSocket streaming
- **Enterprise Security**: Role-based access, audit logging, team management

### Use Cases

1. **Automated Troubleshooting**: Quickly diagnose application failures
2. **Multi-Deployment Apps**: Handle complex apps with multiple components
3. **Cloud-Agnostic Analysis**: Same RCA flow across all cloud providers
4. **Team Collaboration**: Manage teams, applications, and access control
5. **Health Dashboard**: Real-time application status monitoring

---

## 🏗️ Architecture

### High-Level System Design

```
┌─────────────────────────────────────────────────────────────┐
│                    Frontend (React/Vite)                     │
│                     kaiops-ui/                               │
└─────────────────┬───────────────────────────────────────────┘
                  │ HTTP/WebSocket
┌─────────────────▼───────────────────────────────────────────┐
│              FastAPI Backend Server (Port 8000)              │
│                   app/main.py                                │
├─────────────────────────────────────────────────────────────┤
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐       │
│  │  Auth Routes │  │ Chat Routes  │  │ App Routes   │       │
│  └──────────────┘  └──────────────┘  └──────────────┘       │
├─────────────────────────────────────────────────────────────┤
│         Root SRE Agent (orchestration layer)                 │
│         agents/sre_agent/                                    │
│  ┌─────────────────────────────────────────────────────────┐ │
│  │  Coordinates all domain-specific subagents and tools    │ │
│  └─────────────────────────────────────────────────────────┘ │
├─────────────────────────────────────────────────────────────┤
│                    Subagents Layer                            │
│  ┌────────────┐  ┌────────────┐  ┌────────────┐             │
│  │   Azure    │  │    AWS     │  │    GCP     │             │
│  │ RCA Agent  │  │ RCA Agent  │  │ RCA Agent  │             │
│  └────────────┘  └────────────┘  └────────────┘             │
│  ┌────────────┐  ┌────────────┐  ┌────────────┐             │
│  │  Metadata  │  │   ArgoCD   │  │   GitHub   │             │
│  │   Agent    │  │   Agent    │  │   Agent    │             │
│  └────────────┘  └────────────┘  └────────────┘             │
│  ┌────────────┐  ┌────────────┐                             │
│  │  Grafana   │  │ Other Tools │                             │
│  │   Agent    │  │             │                             │
│  └────────────┘  └────────────┘                             │
├─────────────────────────────────────────────────────────────┤
│                     Data Layer                               │
│  ┌──────────────────┐  ┌──────────────────┐                 │
│  │   MongoDB/       │  │     Redis        │                 │
│  │ Cosmos DB        │  │   (Optional)     │                 │
│  │ (Metadata)       │  │   (Caching)      │                 │
│  └──────────────────┘  └──────────────────┘                 │
├─────────────────────────────────────────────────────────────┤
│                 External Cloud APIs                          │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐       │
│  │ Azure Monitor│  │ CloudWatch   │  │ Cloud        │       │
│  │ Container Ins│  │              │  │ Logging &    │       │
│  │              │  │              │  │ Monitoring   │       │
│  └──────────────┘  └──────────────┘  └──────────────┘       │
└─────────────────────────────────────────────────────────────┘
```

### Agent Architecture

Each cloud provider has a dedicated RCA agent:

- **Azure RCA Agent** (`agents/azure_rca_agent/`)
  - Uses MCP-based Azure Monitor integration
  - Queries Container Insights and diagnostic logs
  - Caches results in Redis (5-min TTL)
  
- **AWS RCA Agent** (`agents/aws_rca_agent/`)
  - CloudWatch integration via MCP
  - Analyzes ECS/EKS logs and metrics
  
- **GCP RCA Agent** (`agents/gcp_rca_agent/`)
  - Direct Google Cloud Logging & Monitoring APIs
  - Mock mode for testing (<2 sec response times)
  - Real API calls for production (15-20 sec)

### Multi-Deployment Application Support

Applications can have multiple deployments (e.g., todo app with frontend + backend):

```
Application: "todo"
├── Deployment: todo-frontend-app-deploy
│   ├── Status: 🟢 Healthy
│   ├── CPU: 25%
│   ├── Memory: 40%
│   └── Logs: [INFO messages]
│
└── Deployment: todo-backend-app-deploy
    ├── Status: 🔴 Critical
    ├── CPU: 88%
    ├── Memory: 95%
    └── Logs: [ERROR messages - CrashLoopBackOff]
```

---

## 📁 Project Structure

```
sre-agent-main/
├── sre-agent-backend/               # FastAPI backend server
│   ├── app/                         # FastAPI application
│   │   ├── main.py                  # App initialization and middleware
│   │   ├── models.py                # Data models
│   │   ├── applications/            # Application management routes
│   │   ├── auth/                    # Authentication & authorization
│   │   ├── chat/                    # Chat/RCA interaction routes
│   │   ├── feedback/                # Feedback collection
│   │   ├── metadata/                # Metadata management
│   │   ├── database/                # Database configuration
│   │   ├── middleware/              # Request context, correlation IDs
│   │   ├── cache/                   # Caching layer (L1 + Redis L2)
│   │   ├── exceptions/              # Custom exception hierarchy
│   │   ├── audit/                   # Audit logging
│   │   └── ...                      # Additional utilities
│   │
│   ├── agents/                      # AI agents for RCA
│   │   ├── sre_agent/               # Root orchestrator agent
│   │   │   ├── agent.py             # Main agent definition (26 tools)
│   │   │   ├── prompt.py            # Domain expertise instructions
│   │   │   └── __init__.py
│   │   │
│   │   ├── azure_rca_agent/         # Azure RCA specialist
│   │   │   ├── agent.py
│   │   │   ├── prompt.py            # Azure-specific expertise
│   │   │   ├── tools.py             # Azure analysis tools
│   │   │   ├── mcp_client.py        # MCP server integration
│   │   │   └── app_resolver.py      # App-to-pod mapping
│   │   │
│   │   ├── aws_rca_agent/           # AWS RCA specialist
│   │   │   ├── agent.py
│   │   │   ├── prompt.py
│   │   │   ├── tools.py
│   │   │   ├── mcp_client.py
│   │   │   └── app_resolver.py
│   │   │
│   │   ├── gcp_rca_agent/           # GCP RCA specialist
│   │   │   ├── agent.py
│   │   │   ├── prompt.py            # GCP-specific expertise
│   │   │   ├── tools.py             # 3 main tools
│   │   │   ├── mcp_client.py        # Cloud Logging/Monitoring APIs
│   │   │   ├── config.py            # GCP configuration
│   │   │   ├── app_resolver.py      # App-to-deployment mapping
│   │   │   └── __init__.py
│   │   │
│   │   ├── metadata_agent/          # Metadata lookups
│   │   ├── argocd_agent/            # Deployment orchestration
│   │   ├── github_agent/            # Code repository access
│   │   ├── grafana_agent/           # Monitoring dashboards
│   │   └── ...                      # Other domain agents
│   │
│   ├── argocd-mcp-server/           # ArgoCD MCP server
│   ├── azure-mcp-server/            # Azure Monitor MCP server
│   ├── aws-mcp-server/              # AWS CloudWatch MCP server
│   │
│   ├── run_server.py                # Entry point (starts FastAPI on :8000)
│   ├── requirements.txt             # Python dependencies
│   ├── .env.example                 # Environment variables template
│   └── ...
│
├── kaiops-ui/                       # React frontend
│   ├── src/
│   │   ├── App.jsx                  # Main app component
│   │   ├── main.jsx                 # React entry point
│   │   ├── index.css                # Global styles (Tailwind)
│   │   │
│   │   ├── components/              # React components
│   │   │   ├── ChatHeader.jsx
│   │   │   ├── ChatInput.jsx
│   │   │   ├── ChatBubble.jsx
│   │   │   ├── Sidebar.jsx          # Navigation
│   │   │   ├── Dashboard.jsx        # Main dashboard
│   │   │   ├── ApplicationStats.jsx
│   │   │   ├── UserManagement.jsx
│   │   │   ├── TeamManagement.jsx
│   │   │   ├── Profile.jsx
│   │   │   ├── Login.jsx
│   │   │   ├── Register.jsx
│   │   │   ├── ProtectedRoute.jsx   # Authentication guard
│   │   │   └── ...
│   │   │
│   │   ├── pages/
│   │   │   └── Applications/        # Application management
│   │   │       ├── ApplicationList.jsx
│   │   │       ├── ApplicationForm.jsx
│   │   │       └── ApplicationDetails.jsx
│   │   │
│   │   ├── services/                # API clients
│   │   │   ├── api.js               # Axios base config
│   │   │   ├── auth.js              # Authentication API
│   │   │   ├── chatService.js       # Chat/RCA API
│   │   │   ├── applicationService.js
│   │   │   ├── team.js
│   │   │   └── ...
│   │   │
│   │   ├── contexts/                # React contexts
│   │   │   ├── AuthContext.jsx      # Authentication state
│   │   │   └── FeedbackContext.jsx
│   │   │
│   │   ├── hooks/                   # Custom React hooks
│   │   │   └── useADKStream.js      # WebSocket streaming
│   │   │
│   │   └── constants/               # App constants
│   │       └── apiConstants.js
│   │
│   ├── public/                      # Static assets
│   ├── package.json                 # Node dependencies
│   ├── vite.config.js               # Vite build config
│   ├── tailwind.config.js           # Tailwind CSS config
│   ├── eslint.config.js             # ESLint rules
│   └── .env.example                 # Environment template
│
└── README.md                        # This file
```

---

## ✨ Key Features

### 1. **Multi-Cloud RCA System**
- Unified RCA interface for Azure, AWS, and GCP
- Cloud provider auto-detection from metadata
- Consistent analysis format across all clouds

### 2. **Intelligent Analysis**
- AI-powered root cause analysis
- Multi-deployment application support
- Component health aggregation
- Timeline of failures
- Specific recommendations

### 3. **Real-time Monitoring**
- Live log streaming
- Metric collection and analysis
- Deployment status tracking
- Performance metrics (CPU, Memory)

### 4. **Application Management**
- Register applications with cloud provider details
- Multi-deployment support (frontend, backend, workers, etc.)
- Cloud-specific configuration (GCP Project ID, AWS regions, etc.)
- Application versioning and health tracking

### 5. **Authentication & Authorization**
- JWT-based authentication
- Role-based access control (Admin, Team Lead, Member)
- Team management with role assignments
- Audit logging of all sensitive operations

### 6. **Performance Optimization**
- Two-layer caching (in-memory L1 + Redis L2)
- GCP mock mode for instant testing (<2 sec)
- Container name auto-detection
- Parallel metric queries
- Request correlation IDs for tracing

### 7. **Enterprise Features**
- Feedback collection and review
- User management
- Team collaboration
- Audit trails
- Error handling with safe client messages

---

## 💻 Technology Stack

### Backend
- **Framework**: Google ADK v1.18.0
- **Integration**: Integrated with FastAPI
- **Language**: Python 3.8+
- **API Gateway**: Google ADK (Agent Development Kit)
- **Agents**: OpenAI/Claude-based AI agents
- **Databases**: MongoDB/Cosmos DB (metadata), SQLite (sessions)
- **Caching**: Redis (optional, L2 cache)
- **Cloud APIs**:
  - Azure Monitor Container Insights (MCP)
  - AWS CloudWatch (MCP)
  - Google Cloud Logging & Monitoring (direct APIs)

### Frontend
- **Framework**: React 18.2.0
- **Build Tool**: Vite 5.2.0
- **Styling**: Tailwind CSS 3.4.1
- **Routing**: React Router 6.22.3
- **Animation**: Framer Motion 12.23.24
- **HTTP Client**: Axios 1.6.8
- **3D Effects**: Three.js 0.162.0

### Infrastructure
- **Container Runtime**: Kubernetes (AKS, EKS, GKE)
- **Deployment**: ArgoCD (via MCP server)
- **Monitoring**: Grafana (via MCP server)
- **Version Control**: GitHub (via MCP server)

---

## 🚀 Setup & Installation

### Prerequisites

- **Python 3.8+** (for backend)
- **Node.js 16+** (for frontend)
- **MongoDB** or **Azure Cosmos DB** (for metadata storage)
- **Redis** (optional, for caching)
- **Git**

### Backend Setup

1. **Navigate to backend directory**:
   ```bash
   cd sre-agent-backend
   ```

2. **Create virtual environment**:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

4. **Configure environment variables** (see [Configuration](#configuration) section)

5. **Start the backend server**:
   ```bash
   python run_server.py
   ```
   Backend will start on `http://localhost:8000`
   API docs available at `http://localhost:8000/docs`

### Frontend Setup

1. **Navigate to frontend directory**:
   ```bash
   cd kaiops-ui
   ```

2. **Install dependencies**:
   ```bash
   npm install
   ```

3. **Configure environment variables** (see [Configuration](#configuration) section)

4. **Start development server**:
   ```bash
   npm run dev
   ```
   Frontend will start on `http://localhost:5173` (or another available port)

---

## ⚙️ Configuration

### Backend Environment Variables (`.env`)

```env
# API Configuration
API_PORT=8000
API_HOST=0.0.0.0

# Database
MONGODB_URL=mongodb://localhost:27017/kaiops
MONGODB_DB_NAME=kaiops

# Authentication
SECRET_KEY=your-secret-key-here
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30

# Azure Configuration
AZURE_SUBSCRIPTION_ID=your-subscription-id
AZURE_RESOURCE_GROUP=your-resource-group
AZURE_CLUSTER_NAME=your-aks-cluster
AZURE_COSMOS_CONNECTION_STRING=your-cosmos-connection

# AWS Configuration
AWS_REGION=us-east-1
AWS_ACCESS_KEY_ID=your-access-key
AWS_SECRET_ACCESS_KEY=your-secret-key
AWS_CLUSTER_NAME=your-eks-cluster

# GCP Configuration
GOOGLE_PROJECT_ID=your-gcp-project
GOOGLE_CREDENTIALS_PATH=/path/to/credentials.json
GCP_CLUSTER_NAME=kai-ops
GCP_CLUSTER_ZONE=us-central1-a
GCP_MOCK_MODE=true  # false for real API calls

# Optional: Cloud Monitoring
GCP_MONITORING_ENABLED=true
GCP_LOG_RETENTION_DAYS=30

# Optional: Redis Cache
REDIS_URL=redis://localhost:6379/0
CACHE_TTL_SECONDS=300

# CORS
ALLOWED_ORIGINS=http://localhost:5173,http://localhost:3000

# Logging
LOG_LEVEL=INFO
```

### Frontend Environment Variables (`.env` / `.env.local`)

```env
# Backend API
VITE_API_URL=http://localhost:8000/api/v1
VITE_ADK_API_URL=http://localhost:8000

# Optional: External Integrations
VITE_GITHUB_BASE_URL=https://github.com
VITE_GRAFANA_URL=http://your-grafana:3000
VITE_ARGOCD_BASE_URL=http://your-argocd

# App Configuration
VITE_APP_NAME=sre_agent
VITE_ENVIRONMENT=local
```

---

## 🎮 Running the Application

### Development Mode

**Terminal 1 - Backend**:
```bash
cd sre-agent-backend
python run_server.py
# Output: Starting ADK FastAPI Server...
# Output: API Documentation: http://localhost:8000/docs
```

**Terminal 2 - Frontend**:
```bash
cd kaiops-ui
npm run dev
# Output: VITE v5.2.0  ready in 200 ms
# ➜  Local:   http://localhost:5173/
```

**Access the application**:
- Frontend: `http://localhost:5173`
- Backend API: `http://localhost:8000`
- API Docs: `http://localhost:8000/docs`

### Production Build

**Frontend**:
```bash
cd kaiops-ui
npm run build          # Creates dist/ folder
npm run preview        # Preview production build
```

---

## 📚 API Documentation

### Key Endpoints

#### Authentication
- `POST /api/v1/auth/login` - User login
- `POST /api/v1/auth/register` - User registration
- `POST /api/v1/auth/logout` - User logout
- `GET /api/v1/auth/me` - Get current user

#### Applications
- `GET /api/v1/applications` - List all applications
- `POST /api/v1/applications` - Create new application
- `GET /api/v1/applications/{app_id}` - Get application details
- `PUT /api/v1/applications/{app_id}` - Update application
- `DELETE /api/v1/applications/{app_id}` - Delete application

#### Chat & RCA
- `POST /api/v1/chat/send` - Send chat message
- `WebSocket /api/v1/chat/stream` - Real-time RCA results
- `GET /api/v1/chat/history` - Get chat history

#### Teams
- `GET /api/v1/teams` - List teams
- `POST /api/v1/teams` - Create team
- `POST /api/v1/teams/{team_id}/members` - Add team member

#### Feedback
- `POST /api/v1/feedback` - Submit feedback
- `GET /api/v1/feedback` - Get feedback (admin)

Full API documentation available at: `http://localhost:8000/docs`

---

## 🔄 Multi-Cloud RCA System

### How RCA Works

1. **User Query**: "Can you analyze the gcptodoapp?"

2. **Cloud Detection**:
   - Backend queries MongoDB metadata
   - Identifies: `cloud_provider: "gcp"`, `gcp_project_id: "my-project"`

3. **Route to GCP RCA Agent**:
   - Agent identifies deployments: `todo-frontend`, `todo-backend`
   - Queries Cloud Logging for logs
   - Queries Cloud Monitoring for metrics

4. **Component Analysis**:
   ```
   | Component          | Status      | CPU | Memory | Issues       |
   |--------------------|-------------|-----|--------|--------------|
   | todo-frontend      | 🟢 Healthy  | 25% | 40%    | None         |
   | todo-backend       | 🔴 Critical | 88% | 95%    | CrashLoop    |
   ```

5. **Root Cause Analysis**:
   - Backend showing CrashLoopBackOff status
   - CPU at 88%, Memory at 95%
   - Recent ERROR logs indicate OutOfMemory exception

6. **Response**:
   ```
   📋 Issue Summary
   - Backend deployment is crashing due to memory exhaustion
   - Frontend is healthy and operational
   
   📊 Component Health
   [table showing both components]
   
   🔍 Root Cause
   Pod memory limit (512Mi) is too low for application needs.
   Logs show: "Exception in thread 'main' java.lang.OutOfMemoryError"
   
   💡 Recommendations
   1. Increase pod memory limit to 1Gi
   2. Review application memory leaks
   3. Monitor memory after fix
   ```

### GCP Mock Mode

For testing/demo without API calls:

```bash
# In .env
GCP_MOCK_MODE=true    # <2 second responses with fake data
GCP_MOCK_MODE=false   # Real API calls (15-20 seconds)
```

**Mock Data**:
- Frontend: 🟢 Healthy, 25.3% CPU, 42.1% Memory, INFO logs
- Backend: 🔴 Critical, 88.5% CPU, 95.2% Memory, ERROR logs

---

## 👨‍💻 Development

### Adding a New RCA Agent

1. **Create agent directory**:
   ```
   agents/mycloud_rca_agent/
   ├── __init__.py
   ├── agent.py
   ├── prompt.py
   ├── tools.py
   ├── mcp_client.py (if using MCP)
   └── app_resolver.py
   ```

2. **Implement agent.py** with tools

3. **Add prompt.py** with domain expertise

4. **Register in root agent** (`agents/sre_agent/agent.py`):
   ```python
   from agents.mycloud_rca_agent.tools import (
       check_application_logs as mycloud_check_application_logs,
       analyze_pod_logs as mycloud_analyze_pod_logs
   )
   ```

5. **Update routing logic** in root agent

### Code Style

- **Python**: PEP 8, type hints throughout
- **React**: ESLint configured, Prettier for formatting
- **Naming**: Descriptive names, consistent prefixes
- **Comments**: Docstrings for functions, inline for complex logic

### Running Tests

```bash
# Backend tests
cd sre-agent-backend
python -m pytest

# Frontend tests
cd kaiops-ui
npm test
```

---

## 🐛 Troubleshooting

### Backend Issues

#### 1. MongoDB Connection Failed
```
Error: Failed to connect to MongoDB
```
**Solution**:
- Ensure MongoDB is running: `mongod`
- Check `MONGODB_URL` in `.env`
- Verify network connectivity to Cosmos DB

#### 2. GCP Credentials Not Found
```
Error: Failed to load GCP credentials from path
```
**Solution**:
```bash
export GOOGLE_CREDENTIALS_PATH=/path/to/credentials.json
# OR in .env
GOOGLE_CREDENTIALS_PATH=/path/to/credentials.json
```

#### 3. Agent Tools Not Loading
```
Error: Module 'agents.azure_rca_agent' not found
```
**Solution**:
- Ensure all subagent directories have `__init__.py`
- Run from project root: `cd sre-agent-backend && python run_server.py`
- Check `sys.path` includes agents directory

### Frontend Issues

#### 1. CORS Errors
```
Access to XMLHttpRequest at 'http://localhost:8000/...' blocked by CORS policy
```
**Solution**:
- Add your frontend URL to `ALLOWED_ORIGINS` in backend `.env`
- Default: `http://localhost:5173`

#### 2. WebSocket Connection Failed
```
WebSocket is closed before the connection is established
```
**Solution**:
- Ensure backend server is running on port 8000
- Check firewall/network connectivity
- Verify `VITE_ADK_API_URL` in frontend `.env`

#### 3. Blank Page or 404
```
Cannot GET /
```
**Solution**:
- Run `npm run dev` from `kaiops-ui` directory
- Clear browser cache
- Check console for errors (F12)

### Cloud API Issues

#### 1. GCP: "404 Cannot find metric"
```
Error: 404 Cannot find metric(s) that match type = kubernetes.io/pod/...
```
**Solution**:
- Use container-level metrics: `kubernetes.io/container/...`
- Check metric types with: `gcloud monitoring metrics-descriptors list`
- Enable mock mode temporarily: `GCP_MOCK_MODE=true`

#### 2. Azure: MCP Server Connection Failed
```
Error: Failed to connect to Azure MCP server
```
**Solution**:
- Ensure azure-mcp-server is running
- Check Azure credentials configuration
- Verify network connectivity

#### 3. AWS: Insufficient Permissions
```
Error: User is not authorized to perform: cloudwatch:GetMetricStatistics
```
**Solution**:
- Add CloudWatch permissions to IAM role
- Ensure AWS credentials have sufficient access

---

## 📞 Support & Debugging

### Logs

**Backend logs**:
```bash
# Real-time logs during development
python run_server.py

# JSON structured logs for production
# Check stderr output
```

**Frontend logs**:
```bash
# Browser console (F12)
# Network tab for API calls
# Application tab for localStorage
```

### Health Checks

```bash
# Backend health
curl http://localhost:8000/api/v1/health

# Frontend (just check if it loads)
curl http://localhost:5173

# API docs
curl http://localhost:8000/docs
```

### Debug Mode

**Backend** - Set `LOG_LEVEL=DEBUG` in `.env`

**Frontend** - Add to `main.jsx`:
```javascript
window.__APP_DEBUG__ = true
```

---

## 📄 License

[Add your license information here]

---

## 🤝 Contributing

[Add contributing guidelines here]

---

## 📞 Contact

For questions or issues, please:
1. Check the troubleshooting section
2. Review the API documentation at `/docs`
3. Check backend logs for errors
4. Review browser console for frontend issues

---

## 🎉 Quick Start Checklist

- [ ] Clone repository
- [ ] Install Python 3.8+ and Node.js 16+
- [ ] Backend: Create `.env` and configure credentials
- [ ] Backend: `pip install -r requirements.txt`
- [ ] Backend: `python run_server.py`
- [ ] Frontend: `npm install`
- [ ] Frontend: Create `.env` with `VITE_API_URL`
- [ ] Frontend: `npm run dev`
- [ ] Open `http://localhost:5173` in browser
- [ ] Login with credentials
- [ ] Start analyzing applications

---

**Last Updated**: November 26, 2025
**Version**: 1.0.0
