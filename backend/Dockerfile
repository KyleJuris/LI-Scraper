FROM python:3.11-slim

# System deps for Playwright Chromium
RUN apt-get update && apt-get install -y \
    libnss3 libatk1.0-0 libatk-bridge2.0-0 libdrm2 libxkbcommon0 \
    libxcomposite1 libxdamage1 libxfixes3 libxrandr2 libgbm1 libpango-1.0-0 \
    libasound2 libxshmfence1 libgtk-3-0 libcurl4 ca-certificates fonts-liberation \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt && \
    python -m playwright install --with-deps chromium

COPY app ./app
COPY scripts ./scripts

# Render injects $PORT at runtime
ENV PORT=10000
CMD sh -c "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-10000}"

