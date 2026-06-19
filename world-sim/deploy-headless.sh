#!/bin/bash
# Genesis World Sim - Headless Deployment Script
# Run this on your Ubuntu server

set -e

# Install dependencies
pip install fastapi uvicorn python-dotenv grpcio grpcio-tools httpx numpy 2>/dev/null || pip3 install fastapi uvicorn python-dotenv grpcio grpcio-tools httpx numpy

# Create directories
mkdir -p data/stream/segments data/audio data/scenes

# Set environment
export NVIDIA_API_KEY="${NVIDIA_API_KEY:-REDACTED_API_KEY}"
export INFERENCE_API_KEY="${INFERENCE_API_KEY:-1nfsh-76mkxq7c2xd15f5d5vb5xpw705}"

# Run the server
echo "Starting Genesis World Sim on port 19735..."
echo "Access at http://your-headless-ip:19735/stream"
uvicorn backend.api.main:app --host 0.0.0.0 --port 19735