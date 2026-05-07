**AI IMAGE MATCHING**

**MICROSERVICE**

Developer Technical Guide

Python + FastAPI | OpenCLIP | Qdrant | Redis

Standalone AI microservice - integrates with existing Laravel/Node.js backend

| Version: 1.0 | Language: Python 3.11+ | Status: Draft | Audience: Backend Developer |
| ------------ | ---------------------- | ------------- | --------------------------- |

# **1\. Overview & Purpose**

This document provides complete instructions for building a standalone Python FastAPI microservice that handles AI-powered image matching for product entry. The service is separate from the existing backend and communicates with it over HTTP.

## **1.1 What This Service Does**

- Accepts a product image (captured by shopkeeper camera)
- Converts it into a vector embedding using OpenCLIP
- Searches a Qdrant vector database for visually similar products
- Returns the top matching products with metadata so the form can be auto-filled
- Also handles indexing: when a new product image is uploaded, generates and stores its embedding

## **1.2 What This Service Does NOT Do**

- Does not manage product data - that stays in your existing backend/database
- Does not handle authentication at the application level - secure at network/gateway level
- Does not serve the mobile app directly - all calls come from your existing backend

## **1.3 How It Fits Into Your System**

┌─────────────────────────────────────────────────────────────┐

│ Mobile App │

│ (Shopkeeper captures product photo) │

└────────────────────────┬────────────────────────────────────┘

│ HTTP POST (image)

▼

┌─────────────────────────────────────────────────────────────┐

│ Existing Backend (Laravel / Node.js) │

│ Handles auth, business logic, product DB │

└──────────────┬───────────────────────────┬─────────────────┘

│ HTTP POST │ HTTP GET/POST

│ /products/search-similar │ /products/embedding

▼ ▼

┌─────────────────────────────────────────────────────────────┐

│ Python FastAPI AI Microservice ← THIS SERVICE │

│ OpenCLIP (embedding) + Qdrant (vector search) + Redis │

└──────────────────────────┬──────────────────────────────────┘

│

┌────────────┴────────────┐

▼ ▼

Qdrant DB Local File Storage

(vector embeddings) (product images)

**📘 NOTE**

Your existing backend acts as the bridge between the mobile app and this microservice. The mobile app never calls the AI service directly.

# **2\. Architecture & Technology Stack**

## **2.1 Technology Choices**

| **Component**    | **Technology**                              | **Reason**                                                |
| ---------------- | ------------------------------------------- | --------------------------------------------------------- |
| API Framework    | FastAPI (Python)                            | Async, fast, auto-generates OpenAPI docs                  |
| ---              | ---                                         | ---                                                       |
| AI Model         | OpenCLIP (ViT-B/32)                         | Best open-source model for product image similarity       |
| ---              | ---                                         | ---                                                       |
| Vector Database  | Qdrant                                      | Purpose-built for vector search, scales well, open source |
| ---              | ---                                         | ---                                                       |
| Task Queue       | Redis + RQ (Redis Queue)                    | Async embedding generation without blocking API           |
| ---              | ---                                         | ---                                                       |
| Image Storage    | Local filesystem (current) → S3/R2 (future) | Matches your existing file-based storage                  |
| ---              | ---                                         | ---                                                       |
| Runtime          | Python 3.11+                                | Best ML ecosystem, async support                          |
| ---              | ---                                         | ---                                                       |
| Containerization | Docker + Docker Compose                     | Consistent environments, easy deployment                  |
| ---              | ---                                         | ---                                                       |

## **2.2 Service Boundaries**

**⚠️ WARNING**

The AI microservice must run on its own server or container. It should NOT be installed on the same process as your existing Laravel or Node.js backend. Communication between them is HTTP only.

## **2.3 Data Flow - Search**

Shopkeeper captures photo

│

▼

Backend receives image → calls POST /products/search-similar

│

▼

FastAPI receives image bytes

│

▼

Preprocess image (resize to 224x224, normalize)

│

▼

OpenCLIP encodes image → 512-dimensional float vector

│

▼

Qdrant cosine similarity search (top_k = 10)

│

▼

Return: \[{product_id, score, metadata}\] to backend

│

▼

Backend looks up full product details and returns to mobile app

## **2.4 Data Flow - Indexing New Product**

Shopkeeper uploads new product with image

│

▼

Backend saves product to its own DB, saves image to file storage

│

▼

Backend calls POST /products/embedding {product_id, image_path}

│

▼

FastAPI pushes job to Redis Queue (non-blocking)

│

▼

Worker picks up job → loads image → generates embedding

│

▼

Embedding + product_id + metadata stored in Qdrant

│

▼

Product is now searchable

# **3\. Project Structure**

ai-microservice/

├── app/

│ ├── main.py # FastAPI app entry point

│ ├── config.py # Environment config (paths, Qdrant URL, etc.)

│ ├── models/

│ │ └── clip_model.py # OpenCLIP model loader (singleton)

│ ├── routes/

│ │ ├── embedding.py # POST /products/embedding

│ │ ├── search.py # POST /products/search-similar

│ │ └── reindex.py # POST /products/reindex

│ ├── services/

│ │ ├── image_service.py # Image loading, preprocessing

│ │ ├── qdrant_service.py # Qdrant insert/search/delete

│ │ └── embedding_service.py # Embedding generation logic

│ ├── workers/

│ │ └── embedding_worker.py # Redis Queue worker

│ └── schemas/

│ └── requests.py # Pydantic request/response models

├── tests/

│ ├── test_search.py

│ └── test_embedding.py

├── Dockerfile

├── docker-compose.yml

├── requirements.txt

├── .env.example

└── README.md

# **4\. Setup & Installation**

## **4.1 System Requirements**

| **OS**     | Ubuntu 22.04 LTS (recommended) or any Linux    |
| ---------- | ---------------------------------------------- |
| **Python** | 3.11 or higher                                 |
| **RAM**    | Minimum 4 GB (8 GB recommended for CLIP model) |
| **CPU**    | 4+ cores recommended                           |
| **GPU**    | Optional - CPU-only is fine for moderate load  |
| **Docker** | Docker 24+ and Docker Compose v2+              |
| **Disk**   | 10 GB+ for model weights and images            |

## **4.2 Dependencies - requirements.txt**

\# API Framework

fastapi==0.111.0

uvicorn\[standard\]==0.29.0

python-multipart==0.0.9 # for file uploads

\# AI / ML

open-clip-torch==2.24.0

torch==2.3.0

torchvision==0.18.0

Pillow==10.3.0

\# Vector Database

qdrant-client==1.9.1

\# Task Queue

redis==5.0.4

rq==1.16.2

\# Utilities

python-dotenv==1.0.1

pydantic==2.7.1

httpx==0.27.0

numpy==1.26.4

## **4.3 Environment Variables - .env**

\# Server

HOST=0.0.0.0

PORT=8001

\# Qdrant

QDRANT_HOST=localhost

QDRANT_PORT=6333

QDRANT_COLLECTION=products

\# Redis

REDIS_URL=redis://localhost:6379/0

\# Image Storage

\# Path where product images are stored (your existing file directory)

IMAGE_BASE_PATH=/var/www/your-app/storage/products

\# Model

CLIP_MODEL_NAME=ViT-B-32

CLIP_PRETRAINED=openai

\# Search

DEFAULT_TOP_K=10

SIMILARITY_THRESHOLD=0.70

\# Security

INTERNAL_API_KEY=your-secret-key-here

**✅ TIP**

IMAGE_BASE_PATH should point to the exact directory where your existing backend stores product images. The AI service reads from the same location - no duplication needed.

## **4.4 Docker Compose Setup**

\# docker-compose.yml

version: "3.9"

services:

ai-service:

build: .

ports:

\- "8001:8001"

volumes:

\- /var/www/your-app/storage/products:/images:ro # mount existing image dir read-only

\- ./.env:/app/.env

environment:

\- IMAGE_BASE_PATH=/images

depends_on:

\- qdrant

\- redis

restart: unless-stopped

worker:

build: .

command: python -m app.workers.embedding_worker

volumes:

\- /var/www/your-app/storage/products:/images:ro

\- ./.env:/app/.env

depends_on:

\- qdrant

\- redis

restart: unless-stopped

qdrant:

image: qdrant/qdrant:latest

ports:

\- "6333:6333"

volumes:

\- qdrant_data:/qdrant/storage

restart: unless-stopped

redis:

image: redis:7-alpine

ports:

\- "6379:6379"

restart: unless-stopped

volumes:

qdrant_data:

## **4.5 Dockerfile**

FROM python:3.11-slim

WORKDIR /app

\# Install system dependencies

RUN apt-get update && apt-get install -y \\

libgl1-mesa-glx \\

libglib2.0-0 \\

&& rm -rf /var/lib/apt/lists/\*

\# Install Python dependencies

COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

\# Copy application code

COPY app/ ./app/

\# Default command (overridden for worker in docker-compose)

CMD \["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8001"\]

# **5\. Core Code Implementation**

## **5.1 app/config.py**

from pydantic_settings import BaseSettings

class Settings(BaseSettings):

host: str = "0.0.0.0"

port: int = 8001

qdrant_host: str = "localhost"

qdrant_port: int = 6333

qdrant_collection: str = "products"

redis_url: str = "redis://localhost:6379/0"

image_base_path: str = "/images"

clip_model_name: str = "ViT-B-32"

clip_pretrained: str = "openai"

default_top_k: int = 10

similarity_threshold: float = 0.70

internal_api_key: str = ""

class Config:

env_file = ".env"

settings = Settings()

## **5.2 app/models/clip_model.py - Singleton Model Loader**

**⚠️ WARNING**

The CLIP model is large (~350 MB). Load it once on startup and reuse. Never instantiate it per request.

import open_clip

import torch

from app.config import settings

\_model = None

\_preprocess = None

\_tokenizer = None

def get_model():

global \_model, \_preprocess, \_tokenizer

if \_model is None:

device = "cuda" if torch.cuda.is_available() else "cpu"

\_model, \_, \_preprocess = open_clip.create_model_and_transforms(

settings.clip_model_name,

pretrained=settings.clip_pretrained,

device=device

)

\_model.eval()

\_tokenizer = open_clip.get_tokenizer(settings.clip_model_name)

print(f"CLIP model loaded on {device}")

return \_model, \_preprocess, \_tokenizer

## **5.3 app/services/embedding_service.py**

import torch

import numpy as np

from PIL import Image

from app.models.clip_model import get_model

def generate_embedding_from_path(image_path: str) -> list\[float\]:

"""Load image from disk and return CLIP embedding."""

image = Image.open(image_path).convert("RGB")

return generate_embedding_from_image(image)

def generate_embedding_from_bytes(image_bytes: bytes) -> list\[float\]:

"""Accept raw bytes (camera upload) and return CLIP embedding."""

import io

image = Image.open(io.BytesIO(image_bytes)).convert("RGB")

return generate_embedding_from_image(image)

def generate_embedding_from_image(image: Image.Image) -> list\[float\]:

model, preprocess, \_= get_model()

device = next(model.parameters()).device

tensor = preprocess(image).unsqueeze(0).to(device)

with torch.no_grad():

features = model.encode_image(tensor)

features = features / features.norm(dim=-1, keepdim=True) # normalize

return features.cpu().numpy().flatten().tolist()

## **5.4 app/services/qdrant_service.py**

from qdrant_client import QdrantClient

from qdrant_client.models import (

Distance, VectorParams, PointStruct, Filter, FieldCondition, MatchValue

)

from app.config import settings

client = QdrantClient(host=settings.qdrant_host, port=settings.qdrant_port)

COLLECTION = settings.qdrant_collection

VECTOR_SIZE = 512 # ViT-B/32 output dimension

def ensure_collection():

"""Create Qdrant collection if it does not exist."""

existing = \[c.name for c in client.get_collections().collections\]

if COLLECTION not in existing:

client.create_collection(

collection_name=COLLECTION,

vectors_config=VectorParams(size=VECTOR_SIZE, distance=Distance.COSINE)

)

print(f"Created Qdrant collection: {COLLECTION}")

def upsert_embedding(product_id: str, embedding: list\[float\], metadata: dict):

"""Insert or update a product embedding in Qdrant."""

client.upsert(

collection_name=COLLECTION,

points=\[PointStruct(

id=abs(hash(product_id)) % (2\*\*63), # Qdrant needs integer ID

vector=embedding,

payload={"product_id": product_id, \*\*metadata}

)\]

)

def search_similar(embedding: list\[float\], top_k: int = 10) -> list\[dict\]:

"""Search for similar product vectors. Returns list of matches."""

results = client.search(

collection_name=COLLECTION,

query_vector=embedding,

limit=top_k,

with_payload=True

)

return \[

{"product_id": r.payload.get("product_id"), "score": r.score, "metadata": r.payload}

for r in results

if r.score >= settings.similarity_threshold

\]

def delete_embedding(product_id: str):

"""Remove a product embedding when product is deleted."""

client.delete(

collection_name=COLLECTION,

points_selector=\[abs(hash(product_id)) % (2\*\*63)\]

)

## **5.5 app/main.py**

from fastapi import FastAPI, Request

from fastapi.middleware.cors import CORSMiddleware

from contextlib import asynccontextmanager

from app.services.qdrant_service import ensure_collection

from app.models.clip_model import get_model

from app.routes import embedding, search, reindex, delete

@asynccontextmanager

async def lifespan(app: FastAPI):

\# Startup: warm up model and ensure DB collection exists

print("Loading CLIP model...")

get_model()

ensure_collection()

print("AI Microservice ready.")

yield

\# Shutdown: nothing needed

app = FastAPI(

title="Product Image Matching API",

version="1.0.0",

lifespan=lifespan

)

app.add_middleware(

CORSMiddleware,

allow_origins=\["<http://your-backend-server.com"\>], # restrict to your backend only

allow_methods=\["POST", "DELETE"\],

allow_headers=\["\*"\],

)

app.include_router(embedding.router)

app.include_router(search.router)

app.include_router(reindex.router)

app.include_router(delete.router)

@app.get("/health")

async def health():

return {"status": "ok"}

# **6\. API Endpoints**

## **6.1 POST /products/embedding**

Called by your backend when a new product is created. Queues a background job to generate and store the embedding.

### **Request**

Content-Type: multipart/form-data

Headers: X-Internal-API-Key: &lt;your-secret&gt;

Fields:

product_id string required Unique product identifier from your DB

image_path string optional Relative path in IMAGE_BASE_PATH

image_file file optional Upload the image file directly

metadata JSON optional e.g. {"name":"iPhone 7","category":"phones","sku":"IP7-128"}

Note: Provide either image_path OR image_file, not both.

### **Response**

// Success 202 Accepted

{

"status": "queued",

"product_id": "prod_abc123",

"message": "Embedding job queued successfully"

}

### **Route Code - app/routes/embedding.py**

from fastapi import APIRouter, UploadFile, File, Form, BackgroundTasks, HTTPException

from app.services.embedding_service import generate_embedding_from_path, generate_embedding_from_bytes

from app.services.qdrant_service import upsert_embedding

from app.config import settings

import json, os, redis

from rq import Queue

router = APIRouter()

rq_client = redis.from_url(settings.redis_url)

queue = Queue(connection=rq_client)

@router.post("/products/embedding", status_code=202)

async def create_embedding(

product_id: str = Form(...),

image_path: str = Form(None),

image_file: UploadFile = File(None),

metadata: str = Form("{}"),

):

meta = json.loads(metadata)

if image_file:

image_bytes = await image_file.read()

queue.enqueue("app.workers.embedding_worker.process_from_bytes",

product_id, image_bytes, meta)

elif image_path:

full_path = os.path.join(settings.image_base_path, image_path)

queue.enqueue("app.workers.embedding_worker.process_from_path",

product_id, full_path, meta)

else:

raise HTTPException(400, "Provide image_path or image_file")

return {"status": "queued", "product_id": product_id, "message": "Embedding job queued"}

## **6.2 POST /products/search-similar**

Main endpoint. Called when shopkeeper captures a photo. Returns the most visually similar products.

### **Request**

Content-Type: multipart/form-data

Headers: X-Internal-API-Key: &lt;your-secret&gt;

Fields:

image_file file required Photo captured by shopkeeper camera

top_k int optional Number of results to return (default: 10)

### **Response**

// Success 200 OK

{

"matches": \[

{

"product_id": "prod_abc123",

"score": 0.94,

"metadata": {

"name": "Apple iPhone 7",

"category": "Smartphones",

"sku": "IP7-128-BLK",

"brand": "Apple"

}

},

{

"product_id": "prod_xyz456",

"score": 0.87,

"metadata": { ... }

}

\],

"count": 2

}

### **Route Code - app/routes/search.py**

from fastapi import APIRouter, UploadFile, File, Form

from app.services.embedding_service import generate_embedding_from_bytes

from app.services.qdrant_service import search_similar

from app.config import settings

router = APIRouter()

@router.post("/products/search-similar")

async def search_by_image(

image_file: UploadFile = File(...),

top_k: int = Form(settings.default_top_k)

):

image_bytes = await image_file.read()

embedding = generate_embedding_from_bytes(image_bytes)

matches = search_similar(embedding, top_k=top_k)

return {"matches": matches, "count": len(matches)}

## **6.3 POST /products/reindex**

Admin endpoint. Rebuilds all embeddings from scratch. Use when switching models or after bulk image updates.

@router.post("/products/reindex")

async def reindex_all(background_tasks: BackgroundTasks):

"""Scan IMAGE_BASE_PATH and queue embedding jobs for all found images."""

background_tasks.add_task(\_reindex_task)

return {"status": "reindex started"}

async def \_reindex_task():

import os

base = settings.image_base_path

for filename in os.listdir(base):

if filename.lower().endswith((".jpg", ".jpeg", ".png", ".webp")):

product_id = os.path.splitext(filename)\[0\]

full_path = os.path.join(base, filename)

queue.enqueue("app.workers.embedding_worker.process_from_path",

product_id, full_path, {})

## **6.4 DELETE /products/embedding/{product_id}**

Remove a product vector from Qdrant when the product is deleted from your main database.

@router.delete("/products/embedding/{product_id}")

async def remove_embedding(product_id: str):

from app.services.qdrant_service import delete_embedding

delete_embedding(product_id)

return {"status": "deleted", "product_id": product_id}

## **6.5 Endpoint Summary**

| **Method** | **Endpoint**             | **Caller**    | **When to Call**                     |
| ---------- | ------------------------ | ------------- | ------------------------------------ |
| POST       | /products/embedding      | Your backend  | New product created / image uploaded |
| ---        | ---                      | ---           | ---                                  |
| POST       | /products/search-similar | Your backend  | Shopkeeper captures photo for search |
| ---        | ---                      | ---           | ---                                  |
| POST       | /products/reindex        | Admin / cron  | Bulk reindex or model switch         |
| ---        | ---                      | ---           | ---                                  |
| DELETE     | /products/embedding/{id} | Your backend  | Product deleted from system          |
| ---        | ---                      | ---           | ---                                  |
| GET        | /health                  | Load balancer | Health check                         |
| ---        | ---                      | ---           | ---                                  |

# **7\. Background Worker**

The worker is a separate process that picks up jobs from Redis Queue. It handles the heavy embedding generation without blocking the API response.

## **7.1 app/workers/embedding_worker.py**

from app.services.embedding_service import generate_embedding_from_path, generate_embedding_from_bytes

from app.services.qdrant_service import upsert_embedding

def process_from_path(product_id: str, image_path: str, metadata: dict):

"""Worker job: load image from disk, generate embedding, store in Qdrant."""

try:

embedding = generate_embedding_from_path(image_path)

upsert_embedding(product_id, embedding, metadata)

print(f"\[Worker\] Indexed {product_id} from {image_path}")

except Exception as e:

print(f"\[Worker\] Failed to index {product_id}: {e}")

raise # RQ will mark job as failed and retry

def process_from_bytes(product_id: str, image_bytes: bytes, metadata: dict):

"""Worker job: use uploaded bytes directly."""

try:

embedding = generate_embedding_from_bytes(image_bytes)

upsert_embedding(product_id, embedding, metadata)

print(f"\[Worker\] Indexed {product_id} from uploaded bytes")

except Exception as e:

print(f"\[Worker\] Failed {product_id}: {e}")

raise

## **7.2 Running the Worker**

\# Locally

rq worker --url redis://localhost:6379

\# In Docker (handled by docker-compose worker service)

\# command: python -m app.workers.embedding_worker

**⚠️ WARNING**

Always run at least one worker process. Without it, /products/embedding calls will queue jobs but nothing will process them. In production, run 2-4 workers.

# **8\. Integration with Your Existing Backend**

## **8.1 What Your Backend Needs to Do**

- When a new product image is saved, call POST /products/embedding with product_id, image_path, and any metadata (name, category, SKU, brand)
- When a shopkeeper captures a photo for search, forward the image to POST /products/search-similar and return the results to the mobile app
- When a product is deleted, call DELETE /products/embedding/{product_id}

## **8.2 Example - Laravel**

// ProductController.php

use Illuminate\\Support\\Facades\\Http;

private string \$aiServiceUrl = "<http://ai-service:8001>";

private string \$apiKey = "your-secret-key";

// Called after product is created

public function indexProductImage(Product \$product) {

Http::withHeaders(\["X-Internal-API-Key" => \$this->apiKey\])

\->attach("image_file", file_get_contents(\$product->image_path), "image.jpg")

\->post("{\$this->aiServiceUrl}/products/embedding", \[

"product_id" => \$product->id,

"metadata" => json_encode(\[

"name" => \$product->name,

"category" => \$product->category,

"sku" => \$product->sku,

\])

\]);

}

// Called when shopkeeper submits photo

public function searchByImage(Request \$request) {

\$response = Http::withHeaders(\["X-Internal-API-Key" => \$this->apiKey\])

\->attach("image_file", \$request->file("image")->get(), "query.jpg")

\->post("{\$this->aiServiceUrl}/products/search-similar", \[

"top_k" => 8

\]);

\$matches = \$response->json("matches");

// Enrich with full product data from your DB

return Product::whereIn("id", collect(\$matches)->pluck("product_id"))->get();

}

## **8.3 Example - Node.js / Express**

const FormData = require("form-data");

const axios = require("axios");

const AI_URL = process.env.AI_SERVICE_URL || "<http://ai-service:8001>";

const API_KEY = process.env.INTERNAL_API_KEY;

// Search by image

async function searchByImage(imageBuffer, topK = 8) {

const form = new FormData();

form.append("image_file", imageBuffer, { filename: "query.jpg" });

form.append("top_k", topK);

const { data } = await axios.post(\`\${AI_URL}/products/search-similar\`, form, {

headers: { ...form.getHeaders(), "X-Internal-API-Key": API_KEY }

});

return data.matches;

}

## **8.4 Migrating Existing Products**

Since your product images are already stored in a file directory, run a one-time migration to index all of them:

\# Option 1: Call the reindex endpoint (simplest)

curl -X POST <http://localhost:8001/products/reindex> \\

\-H "X-Internal-API-Key: your-secret"

\# Option 2: Write a migration script that iterates your DB

\# and calls /products/embedding for each product with metadata

**⚠️ WARNING**

The reindex endpoint will scan IMAGE_BASE_PATH and use filenames as product_ids. If your filenames do not match product IDs in your database, use Option 2 and pass the correct product_id and metadata.

# **9\. Security**

## **9.1 API Key Middleware**

The AI service should only accept requests from your backend. Add an API key check:

\# app/middleware/auth.py

from fastapi import Request, HTTPException

from app.config import settings

async def verify_internal_key(request: Request, call_next):

key = request.headers.get("X-Internal-API-Key")

if key != settings.internal_api_key:

raise HTTPException(status_code=403, detail="Forbidden")

return await call_next(request)

\# In main.py, add:

app.middleware("http")(verify_internal_key)

## **9.2 Network Security**

- Run the AI service on an internal network - do not expose port 8001 to the public internet
- Your existing backend should be the only service that can reach the AI microservice
- Use a firewall rule (iptables or cloud security group) to block external access to port 8001
- If using Docker, put both services on the same Docker network and do not publish the AI service port externally

## **9.3 Image Validation**

\# Validate uploaded images before processing

from PIL import Image

import io

ALLOWED_TYPES = {"image/jpeg", "image/png", "image/webp"}

MAX_SIZE_BYTES = 10 \* 1024 \* 1024 # 10 MB

def validate_image(image_bytes: bytes, content_type: str):

if content_type not in ALLOWED_TYPES:

raise ValueError(f"Unsupported image type: {content_type}")

if len(image_bytes) > MAX_SIZE_BYTES:

raise ValueError("Image too large")

Image.open(io.BytesIO(image_bytes)).verify() # raises if corrupt

# **10\. Performance & Scaling**

## **10.1 Expected Performance**

| **Operation**                       | **Expected Time** | **Notes**                      |
| ----------------------------------- | ----------------- | ------------------------------ |
| CLIP embedding generation           | 80-200ms          | CPU-only; ~15ms with GPU       |
| ---                                 | ---               | ---                            |
| Qdrant vector search (10K products) | <10ms             | Very fast even without GPU     |
| ---                                 | ---               | ---                            |
| Qdrant vector search (1M products)  | <50ms             | Still fast with HNSW index     |
| ---                                 | ---               | ---                            |
| End-to-end search response          | 100-300ms         | Acceptable for user experience |
| ---                                 | ---               | ---                            |
| Embedding worker job                | 100-250ms         | Background, does not block API |
| ---                                 | ---               | ---                            |

## **10.2 Scaling Recommendations**

### **Small catalog (< 50K products)**

- Single FastAPI instance + 2 workers + Qdrant on same server
- CPU-only is sufficient
- 4 GB RAM is enough

### **Medium catalog (50K - 500K products)**

- 2-4 FastAPI instances behind a load balancer
- 4-8 workers
- Qdrant on dedicated server or use Qdrant Cloud
- Consider GPU for faster embedding generation

### **Large catalog (500K+)**

- Qdrant Cloud or self-hosted cluster
- GPU server for embedding generation
- Celery instead of RQ for more advanced job control

## **10.3 Model Warmup**

**📘 NOTE**

The CLIP model takes 5-15 seconds to load. The lifespan() function in main.py pre-loads it on startup. Never skip this - cold-loading on first request causes timeouts.

## **10.4 Uvicorn Workers**

\# For production, run multiple uvicorn workers

\# (each loads the CLIP model independently - requires 4+ GB RAM per worker)

uvicorn app.main:app --workers 2 --host 0.0.0.0 --port 8001

\# Or use gunicorn with uvicorn worker class

gunicorn app.main:app -w 2 -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:8001

# **11\. Testing**

## **11.1 Manual Smoke Test**

\# 1. Health check

curl <http://localhost:8001/health>

\# 2. Index a product by file path

curl -X POST <http://localhost:8001/products/embedding> \\

\-H "X-Internal-API-Key: your-secret" \\

\-F "product_id=prod_001" \\

\-F "image_path=iphone7.jpg" \\

\-F 'metadata={"name":"iPhone 7","category":"Phones","sku":"IP7-128"}'

\# 3. Search with a photo

curl -X POST <http://localhost:8001/products/search-similar> \\

\-H "X-Internal-API-Key: your-secret" \\

\-F "image_file=@/path/to/test-photo.jpg" \\

\-F "top_k=5"

\# 4. Delete a product embedding

curl -X DELETE <http://localhost:8001/products/embedding/prod_001> \\

\-H "X-Internal-API-Key: your-secret"

## **11.2 Automated Test Example**

\# tests/test_search.py

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)

HEADERS = {"X-Internal-API-Key": "your-secret"}

def test_health():

r = client.get("/health")

assert r.status_code == 200

def test_search_returns_results():

with open("tests/fixtures/iphone.jpg", "rb") as f:

r = client.post("/products/search-similar",

headers=HEADERS,

files={"image_file": ("iphone.jpg", f, "image/jpeg")},

data={"top_k": 5})

assert r.status_code == 200

assert "matches" in r.json()

\# Run with:

\# pytest tests/ -v

## **11.3 Quality Checks**

- Test with photos taken at different angles - the model should still match
- Test with different lighting conditions (dark room, bright sunlight)
- Test with slightly different product variants (iPhone 7 Black vs iPhone 7 Silver)
- Verify that score threshold (0.70) filters out unrelated products
- Measure search latency under load using locust or wrk

# **12\. Deployment Checklist**

## **12.1 Pre-Deployment**

- Set all environment variables in .env - never commit this file
- Set INTERNAL_API_KEY to a strong random string (min 32 chars)
- Mount existing image directory read-only into the container
- Run one-time migration: call /products/reindex or script each product
- Confirm Qdrant collection is created and has expected vector count
- Test /health endpoint returns 200

## **12.2 Deployment Commands**

\# Start all services

docker-compose up -d

\# Check logs

docker-compose logs -f ai-service

docker-compose logs -f worker

\# Check Qdrant has vectors

curl <http://localhost:6333/collections/products>

\# Scale workers

docker-compose up -d --scale worker=4

## **12.3 Monitoring**

- Qdrant has a built-in web UI at <http://your-server:6333/dashboard>
- RQ Dashboard available via rq-dashboard package for job monitoring
- Add Prometheus metrics to FastAPI using prometheus-fastapi-instrumentator for production monitoring

**⚠️ WARNING**

Keep Qdrant data volume backed up regularly. If Qdrant data is lost, all embeddings need to be regenerated via /products/reindex. The source images are safe in your existing storage.

## **12.4 Upgrading the Model**

If you switch from ViT-B/32 to a better model in the future (e.g. ViT-L/14):

- Update CLIP_MODEL_NAME and CLIP_PRETRAINED in .env
- Update VECTOR_SIZE in qdrant_service.py to match new model output dimension
- Delete and recreate the Qdrant collection
- Call /products/reindex to regenerate all embeddings

**🚫 IMPORTANT**

Different CLIP models produce vectors of different sizes. ViT-B/32 = 512 dimensions. ViT-L/14 = 768 dimensions. You cannot mix embeddings from different models in the same Qdrant collection.