FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN mkdir -p sessions

ENV PYTHONUNBUFFERED=1
ENV API_URL=http://backend:8000
ENV BOT_MAX_WORKERS=8
EXPOSE 8001

CMD ["python", "bot.py"]
