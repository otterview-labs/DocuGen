FROM node:22-bookworm-slim AS frontend
WORKDIR /build
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

FROM python:3.11-slim
WORKDIR /app
COPY pyproject.toml ./
RUN python -c 'import tomllib; print("\n".join(tomllib.load(open("pyproject.toml", "rb"))["project"]["dependencies"]))' > /tmp/requirements.txt
RUN --mount=type=cache,target=/root/.cache/pip pip install -r /tmp/requirements.txt
COPY quill/ quill/
COPY --from=frontend /build/dist/ frontend/dist/
RUN useradd --create-home --uid 10001 quill && mkdir /data && chown quill:quill /data
ENV QUILL_DATA_DIR=/data
USER quill
EXPOSE 8080
CMD ["uvicorn", "quill.main:app", "--host", "0.0.0.0", "--port", "8080", "--workers", "1"]
