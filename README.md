# AI Image Matching Microservice (product-match)

Everystore visual product similarity: **OpenCLIP** embeddings + **vector search**.

**Production** runs on **AWS Lambda + API Gateway** with **Neon pgvector**, **SQS**, and optional **S3** staging. Laravel on Lightsail calls the public API.

Full architecture (local vs remote, Neon/S3 separation, what’s left): **[DEPLOY_AWS.md](DEPLOY_AWS.md)**

## Live API

```
https://0y6bdqfbmd.execute-api.ap-south-1.amazonaws.com
```

Auth: header `X-Internal-API-Key` (same as Laravel `PRODUCT_MATCH_API_KEY`).

## Features

- Image embed + cosine similarity search (ViT-B-32, 512-d)
- Async indexing via SQS (production) or FastAPI BackgroundTasks (local)
- Laravel webhook callback (`INDEXED` / `FAILED`)
- Admin queue / dead-letter endpoints (SQS-backed in prod)

## API endpoints

### Core

| Method | Path | Notes |
|--------|------|--------|
| `POST` | `/products/embedding` | Queue embed (`product_id` + `image_path` URL or `image_file`) → 202 |
| `POST` | `/products/search-similar` | Sync search (multipart `image_file`) |
| `DELETE` | `/products/embedding/{product_id}` | Remove vector |

### System

| Method | Path |
|--------|------|
| `GET` | `/health` |
| `POST` | `/products/reindex` |
| `GET` | `/products/reindex/status` |
| `GET` | `/queue/status` |
| `GET` / `DELETE` | `/queue/dead-letters` |

Swagger (local): [http://localhost:8001/docs](http://localhost:8001/docs)

## Local vs remote (short)

| Concern | Local | Production |
|---------|--------|------------|
| Process | `uvicorn` on your machine | Lambda containers (API / Search / Worker) |
| Vectors | Neon via `DATABASE_URL` (recommended) | **Neon pgvector** (separate from Lightsail) |
| Job queue | In-process BackgroundTasks | **SQS** (+ DLQ) |
| Multipart uploads | Optional | Staged to **S3** (separate bucket), then Worker |
| Product images | Local path or HTTPS URL | **CDN / R2** URLs from Laravel |
| Laravel | Optional callback | Lightsail + PM2 `ai-matching` worker |

Neon (vectors) and S3 (temp uploads) are **separate remote services** — not stored on the Laravel VM or inside Lambda `/tmp` permanently.

## Requirements

- Python >= 3.11
- ~1GB+ RAM for CLIP locally
- `DATABASE_URL` pointing at Neon with `pgvector`

## Run locally

```bash
python -m venv venv
# Windows: .\venv\Scripts\activate
# macOS/Linux: source venv/bin/activate
pip install -r requirements.txt
pip install torch torchvision open-clip-torch

cp .env.example .env
# set DATABASE_URL, INTERNAL_API_KEY
python infra/run_migration.py

python -m uvicorn app.main:app --host 0.0.0.0 --port 8001
```

Leave `SQS_QUEUE_URL` empty for local BackgroundTasks mode.

```bash
curl http://localhost:8001/health
```

## Deploy (AWS)

See **[DEPLOY_AWS.md](DEPLOY_AWS.md)**. Summary:

```powershell
$env:DATABASE_URL = 'postgresql://...@...neon.tech/...?sslmode=require'
$env:INTERNAL_API_KEY = '...'
.\infra\deploy.ps1
```

Stack: `everystore-product-match` · region `ap-south-1`.
