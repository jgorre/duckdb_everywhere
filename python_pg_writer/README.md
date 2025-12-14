# Pancake Backend Service

A FastAPI service for managing pancakes in the CloudNativePG database.

## Overview

This service provides a REST API to interact with the `happy_pancakes` PostgreSQL database running on CloudNativePG.

### Key Connection Details

- **Database Host**: `local-postgres-rw` (CloudNativePG read-write endpoint)
- **Database Name**: `happy_pancakes`
- **Database User**: Pulled from secret `local-postgres-app` with key `username`
- **Database Password**: Pulled from secret `local-postgres-app` with key `password`
- **Port**: 5432

The credentials are automatically managed by CloudNativePG and stored in the `local-postgres-app` secret.

## Local Development

### Prerequisites

- Python 3.11+
- PostgreSQL client libraries

### Setup

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Set environment variables for local testing:
```bash
export DB_USER=jordans_db
export DB_PASSWORD=<your-password>
export DB_HOST=localhost
export DB_PORT=5432
export DB_NAME=happy_pancakes
```

3. Run the application:
```bash
uvicorn main:app --reload
```

The API will be available at `http://localhost:8000`

### API Documentation

Visit `http://localhost:8000/docs` for interactive Swagger UI documentation.

## Kubernetes Deployment

### Prerequisites

- CloudNativePG cluster running with name `local-postgres`
- Docker image built and available

### Build Docker Image

```bash
docker build -t pancake-backend:latest .
```

### Deploy to Kubernetes

```bash
kubectl apply -f kube/01-deployment.yaml
kubectl apply -f kube/02-service.yaml
```

### Access the Service

From within the cluster:
```bash
curl http://pancake-backend:8000/health
```

## API Endpoints

### Health Check
- `GET /health` - Service health status

### Pancake Operations
- `POST /pancakes` - Create a new pancake
- `GET /pancakes` - List all pancakes (supports pagination with `skip` and `limit`)
- `GET /pancakes/{id}` - Get a specific pancake
- `PUT /pancakes/{id}` - Update a pancake
- `DELETE /pancakes/{id}` - Delete a pancake

### Statistics
- `GET /stats` - Get pancake statistics (total count, average fluffiness)

## Example Requests

### Create a Pancake
```bash
curl -X POST http://localhost:8000/pancakes \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Blueberry Bliss",
    "fluffiness_level": 9,
    "syrup_type": "maple",
    "is_buttery": true,
    "magical_factor": 8.5,
    "taste_notes": "Perfectly fluffy with bursts of blueberry"
  }'
```

### List Pancakes
```bash
curl http://localhost:8000/pancakes
```

### Get Stats
```bash
curl http://localhost:8000/stats
```

## Environment Variables

- `DB_USER` - Database username (default: `jordans_db`)
- `DB_PASSWORD` - Database password (default: empty)
- `DB_HOST` - Database host (default: `local-postgres-rw`)
- `DB_PORT` - Database port (default: `5432`)
- `DB_NAME` - Database name (default: `happy_pancakes`)

## Troubleshooting

### Connection Issues
- Ensure the PostgreSQL cluster is running and healthy
- Check that the service can reach `local-postgres-rw` on port 5432
- Verify credentials in the `local-postgres-app` secret

### Database Issues
- Check CloudNativePG logs: `kubectl logs -l cnpg.io/cluster=local-postgres`
- Verify the `happy_pancakes` database exists

## Happy Pancaking! 🥞
