# Stages: base (deps + code), test (runs the tests), app (the game server).
#   docker build --target test .     -> tests; the build fails if a test fails
#   docker compose up -d --build     -> app only (no tests, no dev deps)

FROM python:3.12-slim AS base
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY engine engine
COPY api api
COPY scenariusz scenariusz

FROM base AS test
COPY requirements-dev.txt .
RUN pip install --no-cache-dir -r requirements-dev.txt
COPY tests tests
COPY play.py .
RUN python -m unittest discover -s tests -v

FROM base AS app
# Port next to the IoT hub (8765) on the AP computer
EXPOSE 8766
CMD ["uvicorn", "api.app:app", "--host", "0.0.0.0", "--port", "8766"]
