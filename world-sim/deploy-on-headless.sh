#!/bin/bash
# Run this script on your Ubuntu headless

set -e

cd ~

# Create project directory
mkdir -p genesis-world-sim && cd genesis-world-sim

# Create directory structure
mkdir -p data/stream/segments
mkdir -p backend/providers

# Install dependencies
pip3 install fastapi uvicorn python-dotenv grpcio httpx numpy pillow --quiet

# Create .env with your keys
cat > .env << 'EOF'
WORLD_PROVIDER_MODE=nim-live
VIDEO_PIPELINE_ENABLED=true
NVIDIA_API_KEY=REDACTED_API_KEY
INFERENCE_API_KEY=1nfsh-76mkxq7c2xd15f5d5vb5xpw705
EOF

echo "Setup complete. Now copy your backend/ folder from Windows to ~/genesis-world-sim/"
echo "Then run: uvicorn backend.api.main:app --host 0.0.0.0 --port 19735"