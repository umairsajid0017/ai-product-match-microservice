# Everystore product-match — architecture & ops

Visual product similarity (OpenCLIP + vectors). Laravel talks to this service over HTTP; production runs on **AWS Lambda** in the Everystore account (`ap-south-1`).

## Live endpoint

```
https://0y6bdqfbmd.execute-api.ap-south-1.amazonaws.com
```

Laravel (Lightsail `everystore` server):

```
PRODUCT_MATCH_URL=https://0y6bdqfbmd.execute-api.ap-south-1.amazonaws.com
PRODUCT_MATCH_API_KEY=<same as INTERNAL_API_KEY / SSM>
LARAVEL_CALLBACK_URL=https://backend.everystore.pk/api/internal/ai-matching/callback
```

Admin Re-index button → Redis queue `ai-matching` → PM2 `everystore-worker-ai-matching` → Lambda embed API.

---

## What is local vs remote

```
                    LOCAL (dev laptop / optional)
                    ┌─────────────────────────────┐
                    │  FastAPI + uvicorn (:8001) │
                    │  CLIP model in process RAM  │
                    │  BackgroundTasks (no SQS)   │
                    └──────────────┬──────────────┘
                                   │ DATABASE_URL (optional same Neon)
                                   ▼
┌──────────────────────────────────────────────────────────────────────┐
│                         REMOTE (production)                          │
│                                                                      │
│  Laravel Lightsail (everystore)                                      │
│    · PRODUCT_MATCH_URL → API Gateway                                 │
│    · Redis queue ai-matching + PM2 worker                            │
│    · Callback receiver /api/internal/ai-matching/callback            │
│                                                                      │
│  API Gateway HTTP API (ap-south-1)                                   │
│         │                                                            │
│         ├─ Api Lambda     (enqueue / delete / health / queue)        │
│         ├─ Search Lambda  (CLIP + pgvector search)                   │
│         └─ Worker Lambda  (SQS → CLIP embed → Neon → Laravel CB)     │
│                                                                      │
│  SEPARATE managed services (not on Lightsail, not inside Lambda FS)  │
│    · Neon Postgres + pgvector   → vectors (product_embeddings)       │
│    · S3 staging bucket          → multipart image_file uploads only  │
│    · SQS + DLQ                  → async embed jobs                   │
│    · SSM Parameter Store        → DATABASE_URL + API key             │
│    · Cloudflare R2 / CDN        → product images (URLs from Laravel) │
│                                                                      │
└──────────────────────────────────────────────────────────────────────┘
```

| Piece | Where it lives | Notes |
|-------|----------------|--------|
| **API code + CLIP weights** | Lambda **container image** (ECR) | Baked in Docker; not on Lightsail |
| **Vectors** | **Neon** (separate Postgres + `pgvector`) | Table `product_embeddings`; **not** Qdrant local disk |
| **Async embed queue** | **SQS** + DLQ | Replaces old `task_queue/` files |
| **Upload staging** | **S3** bucket (SAM stack) | Only when client sends `image_file` multipart; Laravel usually sends CDN **URL** |
| **Product photos** | **Cloudflare R2 / cdn.everystore.pk** | Separate from S3 staging; service downloads by URL |
| **Secrets** | **SSM** `/everystore/product-match/*` | Also mirrored into Lambda env at deploy |
| **Laravel app** | **Lightsail** `backend.everystore.pk` | Calls match API; hosts callback |
| **Old Qdrant / systemd host** | `productsmatch.everystore.pk` (Lightsail) | **Deprecated** — commented out in live `.env` |

Neon and S3 are **independent** of each other and of the Laravel VM: Neon holds vectors; S3 only holds temporary embed uploads; images stay on CDN/R2.

---

## AWS stack resources (`everystore-product-match`)

| Resource | Name / pattern |
|----------|----------------|
| Stack | `everystore-product-match` (region `ap-south-1`) |
| Account | Everystore AWS (`466531995183`) |
| ApiUrl | `https://0y6bdqfbmd.execute-api.ap-south-1.amazonaws.com` |
| Lambdas | `…-api`, `…-search`, `…-worker` |
| SQS | `everystore-product-match-embed` + `…-embed-dlq` |
| S3 | `everystore-product-match-stagingbucket-*` (prefix `embed-uploads/`, 3-day expiry) |
| SSM | `/everystore/product-match/database-url`, `/everystore/product-match/internal-api-key` |

IaC: [`infra/template.yaml`](infra/template.yaml) · deploy: [`infra/deploy.ps1`](infra/deploy.ps1) / [`infra/deploy.sh`](infra/deploy.sh)

---

## Local development

What you run **on your machine**:

- Python 3.11+ venv, `uvicorn` on port **8001**
- CLIP loaded in process memory
- Embed jobs via FastAPI **BackgroundTasks** when `SQS_QUEUE_URL` is empty

What stays **remote even in local mode** (recommended):

- Same **Neon** `DATABASE_URL` (or a Neon branch) for vectors — so local and prod share/pgvector schema
- Optional: real CDN image URLs

```bash
cp .env.example .env
# set DATABASE_URL, INTERNAL_API_KEY, LARAVEL_CALLBACK_URL
pip install -r requirements.txt
pip install torch torchvision open-clip-torch   # not fully pinned for Lambda CPU wheels
python -m uvicorn app.main:app --host 0.0.0.0 --port 8001
```

Neon migration (once):

```bash
python infra/run_migration.py
# or: sql/001_product_embeddings.sql
```

Do **not** rely on `qdrant_data/` or file `task_queue/` for production — those paths are legacy.

---

## Production request flow

### Index (Admin Re-index / product save)

1. Laravel `IndexProductImagesJob` on Redis `ai-matching`
2. PM2 `everystore-worker-ai-matching` → `POST /products/embedding` (image URL)
3. Api Lambda → SQS message
4. Worker Lambda → download CDN image → CLIP → upsert Neon → `POST` Laravel callback (`INDEXED` / `FAILED`)
5. Laravel sets `product.ai_status`

### Search (app “match by image”)

1. Client / Laravel → `POST /products/search-similar` (multipart file)
2. Search Lambda → CLIP → Neon cosine query → matches JSON
3. Laravel hydrates approved in-stock products

---

## What’s done vs what’s left

### Done

- [x] Redesign off local Qdrant → Neon pgvector
- [x] Lambda container (API / Search / Worker) + API Gateway
- [x] SQS + DLQ + S3 staging
- [x] Laravel `PRODUCT_MATCH_URL` on live Lightsail (old URL commented)
- [x] Callback URL → `https://backend.everystore.pk/api/internal/ai-matching/callback`
- [x] PM2 `everystore-worker-ai-matching` in `ecosystem.config.cjs`
- [x] Smoke: embed, search with real CDN image, `ai_status=INDEXED`

### Left / follow-ups

- [ ] **Custom domain** — point `productsmatch.everystore.pk` (ACM + API Gateway) instead of raw `execute-api` URL
- [ ] **Dedicated Neon database** — today vectors may share the main Neon DB; prefer `everystore_product_match` (or schema `ai_match`) for isolation
- [ ] **Recreate `product_embeddings` after Prisma push** — model is in `backend/prisma/schema.prisma`; after `prisma db push` run `backend/prisma/sql/product_embeddings_hnsw.sql` (extension + HNSW). Then reindex products from Admin AI Matching.
- [ ] **SSM SecureString** — parameters are String today; rotate to SecureString + IAM tighten
- [ ] **Provisioned concurrency** on Search Lambda if cold starts hurt UX
- [ ] **Backfill** — reindex all historical products from Admin / script (not only newly touched ones)
- [ ] **Decommission** old Lightsail `productsmatch` systemd service when traffic is fully cut over
- [ ] **Sync `PRODUCT_MATCH_URL` into Secrets Manager `ev_env`** if server redeploys overwrite `.env` from secrets
- [ ] **CI** — optional GitHub Action: `sam build` + deploy on merge

---

## Ops cheat sheet

```powershell
# Deploy (from product-match/)
$env:DATABASE_URL = 'postgresql://...'
$env:INTERNAL_API_KEY = '...'
.\infra\deploy.ps1

# Smoke
$env:PRODUCT_MATCH_URL = 'https://0y6bdqfbmd.execute-api.ap-south-1.amazonaws.com'
python infra/smoke_test.py
```

```bash
# Live server
ssh everystore
cd ~/backend.everystore.pk/backend
pm2 list | grep ai-matching
redis-cli llen everystore-database-queues:ai-matching
curl -s "$PRODUCT_MATCH_URL/health"
```

```bash
# Lambda logs
aws logs tail /aws/lambda/everystore-product-match-worker --region ap-south-1 --follow
aws logs tail /aws/lambda/everystore-product-match-search --region ap-south-1 --follow
```

---

## Related paths

| Path | Role |
|------|------|
| [`app/`](app/) | FastAPI + CLIP + Neon/SQS services |
| [`sql/001_product_embeddings.sql`](sql/001_product_embeddings.sql) | Neon schema |
| [`infra/template.yaml`](infra/template.yaml) | SAM / CloudFormation |
| [`Dockerfile`](Dockerfile) | Lambda image (CPU torch + baked CLIP) |
| Laravel `ProductMatchService` | HTTP client to this API |
| Laravel `ecosystem.config.cjs` | PM2 includes `ai-matching` worker |
