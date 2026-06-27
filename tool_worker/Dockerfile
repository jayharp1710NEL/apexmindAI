FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /worker

COPY pyproject.toml ./
RUN pip install --upgrade pip && pip install ".[dev]"

COPY . .

# Run as a non-root user; the executor further strips privileges per job.
RUN useradd --create-home --uid 10001 sandbox
USER sandbox

CMD ["python", "worker.py"]
