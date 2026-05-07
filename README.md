# AI Image Matching Microservice

Most of the systems require this kind of system. A lightweight, zero-dependency AI-assisted image matching microservice designed to find visually similar items from uploaded images using advanced computer vision models.

## About the project
This Image Matching Microservice solves the problem of manual item identification and entry by allowing users to simply upload an image for comparison. It serves as a backend AI engine that generates image embeddings and performs rapid vector similarity searches. Designed with a strict "Zero-Dependency" architecture, it avoids heavy infrastructure (like Docker, Redis, or dedicated database servers) to minimize CPU usage, RAM consumption, and server costs while maintaining lightning-fast performance.

## Features
- **Zero External Dependencies**: Runs entirely as a single Python process. No Docker, Redis, or Qdrant servers required.
- **Fast Similarity Search**: Uses Qdrant Local Mode for sub-millisecond vector lookups directly on the filesystem.
- **Persistent Crash Recovery**: Features a file-based task queue with atomic writes, ensuring no embedding jobs are lost if the server restarts.
- **Zero-Downtime Reindexing**: Utilizes shadow collections to rebuild the entire database in the background while the live system continues to serve search requests uninterrupted.
- **Smart Queue Management**: Includes pre-queue image validation, deduplication of indexing requests, and a dead-letter queue for corrupted files to prevent infinite retry loops.
- **Clean Architecture**: Built with FastAPI using a modern MVC-style Controller architecture for easy maintenance.

## Requirements
- **Runtime Environment**: Python >= 3.11
- **Supported Platforms**: Windows, macOS, Linux (Standard Python environment)
- **Hardware Considerations**: 
  - Minimum 1GB available RAM (The OpenCLIP model requires ~600MB of RAM loaded in memory)
  - Fast SSD recommended for optimal Qdrant Local Mode performance

## API Endpoints
The system provides a clear set of endpoints for indexing, searching, and managing the background tasks:

### Core Endpoints
- **`POST /products/embedding`**: Upload an image to generate its embedding and add it to the database for future searches.
- **`POST /products/search-similar`**: Upload an image to find visually similar items already stored in the database.
- **`DELETE /products/embedding/{product_id}`**: Remove an item from the database so it no longer appears in search results.

### System & Maintenance
- **`POST /products/reindex`**: Start a background job to completely rebuild the database without affecting live search.
- **`GET /products/reindex/status`**: Check the progress of an ongoing reindex job.
- **`GET /health`**: A simple check to confirm the server is running and healthy.

### Queue Management
- **`GET /queue/status`**: View the number of pending or processing image tasks.
- **`GET /queue/dead-letters`**: View tasks that permanently failed (e.g., due to corrupted images).
- **`DELETE /queue/dead-letters`**: Clear out the list of permanently failed tasks.

## Running the project

### 1. Clone the repository
```bash
git clone <repository-url>
cd product-match
```

### 2. Install dependencies
It is highly recommended to use a virtual environment.
```bash
# Create virtual environment
python -m venv venv

# Activate it (Windows)
.\venv\Scripts\activate
# Activate it (macOS/Linux)
source venv/bin/activate

# Install required packages
pip install -r requirements.txt
```

### 3. Run locally
Start the FastAPI server using Uvicorn.
```bash
python -m uvicorn app.main:app --port 8001
```

### 4. Additional setup
- **Environment Variables**: Copy the sample environment file to configure your paths and keys.
  ```bash
  cp .env.example .env
  ```
  Ensure you set `INTERNAL_API_KEY` for secure access and `IMAGE_BASE_PATH` to point to your local image directory.
- **Database**: Qdrant Local Mode automatically creates and manages the `qdrant_data/` folder upon the first run. No manual initialization is required.

### 5. Verify the application
- **Swagger Documentation**: Open your browser and navigate to [http://localhost:8001/docs](http://localhost:8001/docs) to view and test all endpoints interactively.
- **Health Check**: Run a quick status check in your terminal:
  ```bash
  curl http://localhost:8001/health
  ```
- **Queue Status**: Monitor the background task queue:
  ```bash
  curl http://localhost:8001/queue/status
  ```

---
**Note for Windows Users:** You may occasionally see a harmless `ModuleNotFoundError: import of msvcrt halted` warning on shutdown. This is related to the internal file locking mechanism used by the local database and can be safely ignored.
