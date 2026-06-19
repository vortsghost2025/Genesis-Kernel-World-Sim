# Deploy Genesis World Sim to Headless

## Quick Setup on Ubuntu Headless

SSH into your headless and run these commands:

```bash
# Create project directory
mkdir -p ~/genesis-world-sim && cd ~/genesis-world-sim

# Create the backend structure
mkdir -p backend/{agents,api,providers,world,memory}
mkdir -p data/{stream/segments,audio,scenes,events,mechanics,memories}
mkdir -p frontend

# Install dependencies (run this)
pip3 install fastapi uvicorn python-dotenv grpcio grpcio-tools httpx numpy pillow

# Get the project files (upload the S:/Genesis Kernel World Sim/world-sim/backend folder)
# Or use git clone if you commit this
```

## Run the Server

```bash
# Set environment variables
export NVIDIA_API_KEY="REDACTED_API_KEY"
export INFERENCE_API_KEY="1nfsh-76mkxq7c2xd15f5d5vb5xpw705"

# Run uvicorn
uvicorn backend.api.main:app --host 0.0.0.0 --port 19735
```

## Auto-start on Boot

Create `/etc/systemd/system/genesis-world-sim.service`:

```ini
[Unit]
Description=Genesis World Sim
After=network.target

[Service]
Type=simple
User=we4free
WorkingDirectory=/home/we4free/genesis-world-sim
Environment="NVIDIA_API_KEY=REDACTED_API_KEY"
Environment="INFERENCE_API_KEY=1nfsh-76mkxq7c2xd15f5d5vb5xpw705"
ExecStart=/usr/bin/python3 -m uvicorn backend.api.main:app --host 0.0.0.0 --port 19735
Restart=always

[Install]
WantedBy=multi-user.target
```

Then:
```bash
sudo systemctl daemon-reload
sudo systemctl enable genesis-world-sim
sudo systemctl start genesis-world-sim
```

## Access the Stream

Once running, open in browser:
- `http://YOUR_HEADLESS_IP:19735/stream` - Video stream page
- `http://YOUR_HEADLESS_IP:19735/stream/status` - JSON status
- `http://YOUR_HEADLESS_IP:19735/api/tick` - Trigger tick (POST)

## Port Forwarding (if needed)

If your headless is behind a router, forward port 19735 to the server IP.