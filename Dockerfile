# Stages: base (deps + code), audio (Piper, voice model, narrator recordings
# of the built-in games), test (runs the tests, with Piper), app (the game
# server; Piper and the model stay in it - the game creator records new games
# while running, docs/kreator-gier.md).
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
COPY kreator kreator
COPY rysownik rysownik
COPY scenariusz scenariusz

FROM base AS audio
COPY requirements-audio.txt .
RUN pip install --no-cache-dir -r requirements-audio.txt
COPY tools tools
# A scenario with errors (e.g. a scene text too long for the screen) stops the build
RUN python -m engine.check scenariusz/*.md
# The model goes into the image too (/app/models) - recording works offline
RUN --mount=type=cache,target=/cache \
    python -m tools.nagraj --models /cache/models --cache /cache/wav --out /app/audio scenariusz/*.md \
    && mkdir -p /app/models && cp /cache/models/*.onnx /cache/models/*.onnx.json /app/models/
ENV AP_GRA_MODELS=/app/models

FROM audio AS test
COPY requirements-dev.txt .
RUN pip install --no-cache-dir -r requirements-dev.txt
COPY tests tests
COPY play.py .
RUN python -m unittest discover -s tests -v

FROM audio AS app
# Port next to the IoT hub (8765) on the AP computer
EXPOSE 8766
CMD ["uvicorn", "api.app:app", "--host", "0.0.0.0", "--port", "8766"]
