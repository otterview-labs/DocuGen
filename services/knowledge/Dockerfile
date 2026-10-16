FROM python:3.11-slim
RUN apt-get update && apt-get install -y --no-install-recommends libmagic1 && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY requirements.quill.txt ./
RUN pip install --no-cache-dir -r requirements.quill.txt
COPY app/ app/
COPY main.py ./
RUN useradd --create-home --uid 10001 quill && mkdir storage && chown -R quill:quill storage
USER quill
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8006", "--workers", "1"]
