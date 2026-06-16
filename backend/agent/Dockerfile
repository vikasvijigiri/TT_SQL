FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
EXPOSE 8001
HEALTHCHECK --interval=20s --timeout=10s --retries=3 \
  CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://localhost:8001/api/health')"]
CMD ["sh", "-c", "uvicorn agent.app.api:app --host 0.0.0.0 --port ${PYTHON_PORT:-8001}"]
