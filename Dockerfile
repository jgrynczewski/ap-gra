FROM python:3.12-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY engine engine
COPY api api
COPY scenariusz scenariusz

# Port next to the IoT hub (8765) on the AP computer
EXPOSE 8766
CMD ["uvicorn", "api.app:app", "--host", "0.0.0.0", "--port", "8766"]
