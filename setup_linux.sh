#!/bin/bash

# Exit on error
set -e

echo "--- Setting up AI Microservice on Linux ---"

# 1. Check for Python 3.11+
if ! command -v python3 &> /dev/null; then
    echo "Error: python3 not found. Please install Python 3.11 or higher."
    exit 1
fi

# 2. Create virtual environment
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
fi

# 3. Activate and install dependencies
echo "Installing dependencies (this may take a minute for AI models)..."
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

# 4. Create necessary directories
mkdir -p qdrant_data
mkdir -p task_queue/uploads

# 5. Handle environment variables
if [ ! -f ".env" ]; then
    echo "Creating .env from example..."
    cp .env.example .env
    echo "IMPORTANT: Please edit .env and set your INTERNAL_API_KEY."
fi

echo "--- Setup Complete ---"
echo "To start the service manually: source venv/bin/activate && python3 -m uvicorn app.main:app --host 0.0.0.0 --port 8001"
