FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app
COPY pytest.ini ./pytest.ini
COPY tests ./tests
COPY scripts ./scripts

# The repo-level scenarios/ directory is mounted at /app/scenarios by
# docker-compose (see compose file) so builtin scenarios load on startup.

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
