FROM python:3.12-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    MUJOCO_GL=osmesa \
    PYOPENGL_PLATFORM=osmesa \
    OMP_NUM_THREADS=1 \
    OPENBLAS_NUM_THREADS=1 \
    LP_NUM_THREADS=1 \
    SIM_WORKERS=1 \
    GRADIO_ANALYTICS_ENABLED=False \
    GRADIO_SERVER_NAME=0.0.0.0 \
    GRADIO_SERVER_PORT=7860

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        libosmesa6 libgl1 libglfw3 libglib2.0-0 ffmpeg \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements-sim.txt requirements-ai.txt requirements-ui.txt ./
RUN python -m pip install --no-cache-dir -r requirements-ui.txt

RUN useradd --create-home --uid 1000 appuser
COPY --chown=appuser:appuser . /app
RUN mkdir -p /app/runs /app/exports \
    && chown appuser:appuser /app/runs /app/exports
USER appuser

EXPOSE 7860
CMD ["python", "serve.py"]
