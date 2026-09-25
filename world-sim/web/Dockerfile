FROM python:3.12-slim

WORKDIR /app

COPY web/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# app.py resolves the viewer page relative to its parent dir
# (WORLD_SIM/viewer/index.html), so the image mirrors that layout:
#   /app/web/app.py          <- the Flask app + packaged snapshot
#   /app/viewer/index.html   <- the two-civilization viewer page
# Build with the world-sim dir as context (see README):
#   docker build -f world-sim/web/Dockerfile -t genesis-viewer world-sim/
COPY web/ /app/web/
COPY viewer/ /app/viewer/

EXPOSE 8000

ENV GENESIS_MODE=demo GENESIS_PORT=8000
CMD ["python", "web/app.py"]
