# Deploy product-match (AWS Lambda + API Gateway)

## Public API (live)

```
https://0y6bdqfbmd.execute-api.ap-south-1.amazonaws.com
```

Set Laravel:

```
PRODUCT_MATCH_URL=https://0y6bdqfbmd.execute-api.ap-south-1.amazonaws.com
PRODUCT_MATCH_API_KEY=<same as SSM /everystore/product-match/internal-api-key>
```

## Architecture

API Gateway HTTP API → Lambda (container) → Neon pgvector + SQS worker.

| Function | Role |
|----------|------|
| `everystore-product-match-api` | health, enqueue embed, delete, queue admin |
| `everystore-product-match-search` | sync CLIP + pgvector search |
| `everystore-product-match-worker` | SQS embed jobs + Laravel callback |

## Neon

SQL: [`sql/001_product_embeddings.sql`](sql/001_product_embeddings.sql)

```bash
# PowerShell / bash — requires DATABASE_URL
python infra/run_migration.py
```

`ensure_collection()` also creates the table on startup if missing.

## Deploy (Everystore account, ap-south-1)

Prerequisites: AWS CLI credentials, Docker Desktop, SAM CLI.

Secrets are stored in SSM:

- `/everystore/product-match/database-url`
- `/everystore/product-match/internal-api-key`

```powershell
$env:DATABASE_URL = 'postgresql://...neon.tech/...?sslmode=require'
$env:INTERNAL_API_KEY = '<same as Laravel PRODUCT_MATCH_API_KEY>'
.\infra\deploy.ps1
```

Or:

```bash
export DATABASE_URL='...'
export INTERNAL_API_KEY='...'
bash infra/deploy.sh
```

## Smoke test

```powershell
$env:PRODUCT_MATCH_URL = 'https://0y6bdqfbmd.execute-api.ap-south-1.amazonaws.com'
$env:INTERNAL_API_KEY = '...'
$env:DATABASE_URL = '...'
python infra/smoke_test.py
```

## Local (no Lambda)

```bash
cp .env.example .env   # set DATABASE_URL + INTERNAL_API_KEY
pip install -r requirements.txt
# also: pip install torch torchvision open-clip-torch
python -m uvicorn app.main:app --host 0.0.0.0 --port 8001
```

With `SQS_QUEUE_URL` empty, embed jobs run via FastAPI BackgroundTasks.
