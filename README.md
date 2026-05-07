# Everystore — AI Image Matching Microservice

Lightweight AI-assisted product matching system. Uses CLIP embeddings + Qdrant vector search to find visually similar products from a shopkeeper's photo.

## Architecture

- **API**: FastAPI (Python 3.11+)
- **AI Model**: OpenCLIP ViT-B/32 (512-dim embeddings)
- **Vector DB**: Qdrant (cosine similarity search)
- **Queue**: Redis + RQ (async embedding generation)
- **Storage**: Local filesystem (`../orig_images`)

## Quick Start (Local Development)

```bash
# 1. Create and activate virtual environment
python -m venv venv
.\venv\Scripts\activate   # Windows

# 2. Install dependencies
pip install -r requirements.txt

# 3. Start Qdrant and Redis (Docker)
docker run -d -p 6333:6333 qdrant/qdrant:latest
docker run -d -p 6379:6379 redis:7-alpine

# 4. Start the API server
uvicorn app.main:app --port 8001 --reload

# 5. Start the background worker (separate terminal)
rq worker --url redis://localhost:6379

# 6. Health check
curl http://localhost:8001/health
```

## API Endpoints

| Method | Endpoint                       | Purpose                          |
|--------|--------------------------------|----------------------------------|
| POST   | /products/embedding            | Index a new product image        |
| POST   | /products/search-similar       | Search by photo                  |
| POST   | /products/reindex              | Rebuild all embeddings           |
| DELETE | /products/embedding/{id}       | Remove a product embedding       |
| GET    | /health                        | Health check                     |

## Docker Deployment

```bash
docker-compose up -d
docker-compose logs -f ai-service
docker-compose up -d --scale worker=4  # scale workers
```

## Environment Variables

See `.env.example` for all available configuration options.
