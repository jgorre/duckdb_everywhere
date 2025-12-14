# Pancake Data Pipeline - AI Coding Agent Instructions

## Project Purpose & Scope

This is a **learning project** serving dual goals:
1. **Learning Kubernetes**: Master container orchestration, service networking, secrets management, stateful workloads
2. **Building a Data Pipeline**: Learn the full lifecycle from data ingestion → storage → extraction → modeling → consumption in BI layer

### Current Architecture (Foundation Phase)
The project currently focuses on the **data ingestion and storage layer**:
- **Data Source**: Static HTML/CSS/JS frontend (`pancake` records)
- **Ingestion**: FastAPI REST API validates and writes to database
- **Storage**: CloudNativePG 0_postgresQL cluster (Kubernetes-native)
- **K8s Skills**: Deployments, Services, Secrets, StatefulSets, DNS service discovery

### Future Data Pipeline Components (Planned)
- **Data Extraction**: ETL jobs to export pancake records (CSV, Parquet, etc.)
- **Data Modeling**: Transform raw pancake data into dimensional models (star schema)
- **Orchestration**: Kubernetes CronJobs for scheduled data pipeline runs
- **BI/Analytics Layer**: Consumption layer (Superset, Grafana, or similar)

### Current Architecture: 0_postgresQL ↔ FastAPI ↔ Static Frontend
The backend connects to `local-0_postgres-rw` (CloudNativePG read-write endpoint). Credentials are stored in K8s secret `local-0_postgres-app` with keys `username` and `password`.

## Developer Workflows - Phase 1: Ingestion & Storage

### Local Development (Testing Ingestion Layer)
```bash
# 1. Set environment variables for local DB connection
export DB_USER=jordans_db DB_PASSWORD=<pwd> DB_HOST=localhost DB_PORT=5432 DB_NAME=happy_pancakes

# 2. Start backend with hot reload
cd 1_python_pancake_app && uvicorn main:app --reload

# Frontend: Browser to http://localhost:8000
```

### Kubernetes Deployment (Stateful Storage + Microservice)
- **Database**: `0_postgres/kube/01-cluster.yaml` defines 2-instance 0_postgresQL cluster with 1Gi storage (CloudNativePG StatefulSet)
- **App**: `1_python_pancake_app/kube/{01-deployment.yaml,02-service.yaml}` deploy FastAPI service on NodePort 30090
- Deploy with: `kubectl apply -f 0_postgres/kube/ && kubectl apply -f 1_python_pancake_app/kube/`
- **K8s Concepts Exercised**: StatefulSets (0_postgres), Deployments (app), Services, ConfigMaps, Secrets, DNS discovery

### Health Checks
- Backend: `GET /health` returns `{"status": "healthy", "service": "pancake-backend"}`
- Kubernetes uses HTTP liveness/readiness probes on same endpoint (10s interval)

## Code Patterns & Conventions

### Database Connection (SQLAlchemy + 0_postgresQL)
- Connection string built from env vars in [main.py](../1_python_pancake_app/main.py) (lines 18-26)
- Engine initialized with connection pooling; sessions managed via dependency injection
- Pancake schema mirrors K8s `pancakes` table: `id` (PK), `name`, `fluffiness_level` (1-10), `syrup_type`, `is_buttery`, `magical_factor`, `created_at`, `taste_notes`

### API Endpoints Pattern
- **Models**: Pydantic (e.g., `PancakeCreate`, `PancakeResponse`) for request/response validation
- **CORS**: Enabled globally with `allow_origins=["*"]` (frontend-backend communication)
- Current endpoints: `GET /api/pancakes` (list), `POST /api/pancakes` (create), `GET /` (serve UI), `GET /health`
- Reference: [main.py API section](../1_python_pancake_app/main.py) (lines 105-130)

### Frontend Integration
- Static files served from [1_python_pancake_app/static/](../1_python_pancake_app/static/) via `StaticFiles` mount
- Frontend calls `http://localhost:8000/api/pancakes` for data (see [index.html](../1_python_pancake_app/static/index.html) form)

## Key Files & Responsibilities

| File | Purpose |
|------|---------|
| [0_postgres/kube/01-cluster.yaml](../0_postgres/kube/01-cluster.yaml) | CloudNativePG schema: pancakes table + user grants |
| [1_python_pancake_app/main.py](../1_python_pancake_app/main.py) | FastAPI app, SQLAlchemy ORM, all endpoints |
| [1_python_pancake_app/kube/01-deployment.yaml](../1_python_pancake_app/kube/01-deployment.yaml) | K8s Deployment: mounts DB secrets, env vars |
| [1_python_pancake_app/static/{index.html,app.js}](../1_python_pancake_app/static/) | Frontend forms & AJAX calls to `/api/pancakes` |
| [1_python_pancake_app/requirements.txt](../1_python_pancake_app/requirements.txt) | FastAPI, SQLAlchemy, psycopg2, Pydantic |

## Integration Points & Dependencies

1. **DB Credentials**: K8s secret `local-0_postgres-app` → Deployment env vars `DB_USER`, `DB_PASSWORD`
2. **Service Discovery**: Pod resolves `local-0_postgres-rw` DNS (CloudNativePG managed)
3. **Health Probes**: K8s runs periodic `GET /health` requests (don't remove this endpoint)
4. **CORS**: Frontend on same host (port 8000) but static ≠ API calls require CORS headers

## Before Modifying Code

- **Schema changes**: Update both [0_postgres/kube/01-cluster.yaml](../0_postgres/kube/01-cluster.yaml) `pancakes` table AND [main.py](../1_python_pancake_app/main.py) `Pancake` class (bidirectional sync required)
- **New endpoints**: Add corresponding Pydantic model, follow `/api/` prefix convention
- **Dependencies**: Add to [requirements.txt](../1_python_pancake_app/requirements.txt), rebuild Dockerfile
- **Env vars**: Document in [README.md](../1_python_pancake_app/README.md) and sync with [01-deployment.yaml](../1_python_pancake_app/kube/01-deployment.yaml)
- **Future pipeline additions** (extraction, modeling, BI): Consider Kubernetes CronJobs for ETL, new Deployments for processing services, and ConfigMaps for pipeline configuration
