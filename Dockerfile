# SimToReal Agent operator page. MuJoCo renders on the CPU with OSMesa, so no GPU is needed in the container;
# model inference runs on AMD Token Factory through LLM_BASE_URL / VLM_BASE_URL.
FROM python:3.12-slim-bookworm

RUN apt-get update \
    && apt-get install -y --no-install-recommends libosmesa6 libgl1 libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

ENV MUJOCO_GL=osmesa \
    PYOPENGL_PLATFORM=osmesa \
    GRADIO_SERVER_NAME=0.0.0.0 \
    GRADIO_SERVER_PORT=7860 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

# Non-root user with UID 1000 (also what Hugging Face Spaces expects).
RUN useradd --create-home --uid 1000 app
WORKDIR /app

COPY requirements-sim.txt requirements-ai.txt requirements-ui.txt ./
RUN pip install -r requirements-ui.txt

COPY --chown=app . .
RUN mkdir -p runs exports && chown app runs exports
USER app

EXPOSE 7860
CMD ["python", "app.py"]
