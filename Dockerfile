# Stages: base (deps + code), test (runs the tests), audio (narrator
# recordings, Piper), app (the game server with the recordings).
#   docker build --target test .     -> tests; the build fails if a test fails
#   docker compose up -d --build     -> app (records only new / changed texts)
# Needs BuildKit (Docker 23+ default): the recordings and the voice model are
# kept in a build cache between builds.

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
COPY tools tools
COPY play.py .
RUN python -m unittest discover -s tests -v

FROM base AS audio
COPY requirements-audio.txt .
RUN pip install --no-cache-dir -r requirements-audio.txt
COPY tools tools
RUN --mount=type=cache,target=/cache \
    python -m tools.nagraj --models /cache/models --cache /cache/wav --out /app/audio scenariusz/*.md

FROM base AS app
COPY --from=audio /app/audio audio
# Port next to the IoT hub (8765) on the AP computer
EXPOSE 8766
CMD ["uvicorn", "api.app:app", "--host", "0.0.0.0", "--port", "8766"]
