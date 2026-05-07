# Everystore — AI Image Matching Microservice (Zero-Dependency Version)

Lightweight AI-assisted product matching system. Uses CLIP embeddings + Qdrant (Local Mode) to find visually similar products from a shopkeeper's photo.

**This version requires NO Docker, NO Qdrant server, and NO Redis server.** Everything runs in a single Python process using local file storage.

## Architecture

- **API**: FastAPI (Python 3.11+)
- **AI Model**: OpenCLIP ViT-B/32 (512-dim embeddings)
- **Vector DB**: Qdrant (Local Mode — stores vectors in `qdrant_data/` folder)
- **Background Tasks**: FastAPI Native BackgroundTasks (No Redis needed)
- **Storage**: Local filesystem (`../orig_images`)

## Quick Start (Local Development)

```bash
# 1. Create and activate virtual environment
python -m venv venv
.\venv\Scripts\activate   # Windows

# 2. Install dependencies
pip install -r requirements.txt

# 3. Start the API server
uvicorn app.main:app --port 8001 --reload

# 4. Health check
curl http://localhost:8001/health
```

## How it works (Simplified)
1. **Offline Processing**: When a product is indexed (`POST /products/embedding`), the server generates the embedding and saves it to a local folder called `qdrant_data/`.
2. **Online Search**: When a photo is uploaded for search, the server generates one embedding and does a lightning-fast lookup against the local files.

## API Endpoints

| Method | Endpoint                       | Purpose                          |
|--------|--------------------------------|----------------------------------|
| POST   | /products/embedding            | Index a new product image        |
| POST   | /products/search-similar       | Search by photo                  |
| POST   | /products/reindex              | Rebuild all embeddings           |
| DELETE | /products/embedding/{id}       | Remove a product embedding       |
| GET    | /health                        | Health check                     |

## Environment Variables

See `.env.example` for all available configuration options. (Note: Redis settings are no longer used).
