FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# the app serves: its own code, the viewer HTML (../viewer/index.html),
# and a packaged snapshot (./viewer_data.js). The image expects the repo
# layout; the Dockerfile is built with the world-sim dir as context.
COPY . /app/web

EXPOSE 8000

ENV GENESIS_MODE=demo GENESIS_PORT=8000
CMD ["python", "web/app.py"]
