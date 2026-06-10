# syntax=docker/dockerfile:1
# HuggingFace Spaces Docker deployment.
# Exposes port 7860 (HF default). CPU-only PyTorch keeps the image ~1.5 GB
# smaller than the default CUDA wheel.

FROM python:3.11-slim

# HF Spaces: point all caches to /tmp (always writable, survives the build).
ENV HF_HOME=/tmp/hf_cache \
    TRANSFORMERS_CACHE=/tmp/hf_cache \
    HF_HUB_CACHE=/tmp/hf_cache \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

# Copy dependency manifest first for layer-cache efficiency.
COPY pyproject.toml ./
COPY src/ ./src/

# 1. CPU-only PyTorch (~220 MB) — must come before the general install so pip
#    doesn't pull the CUDA wheel (~2 GB) when resolving torch>=2.0.
RUN pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu

# 2. Everything else (fastapi, transformers, langgraph, …).
RUN pip install --no-cache-dir -e "."

EXPOSE 7860

CMD ["uvicorn", "priormail.main:app", "--host", "0.0.0.0", "--port", "7860"]
