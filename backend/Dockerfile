# NetraCare Iteration 2 backend: FastAPI + SQLite + LangChain. Data packs 1 and 2 are copied in; the database lives on a volume at /data.
# The API key is NOT in this image: docker-compose passes backend/.env to the container at run time (see .dockerignore).
FROM python:3.12-slim

WORKDIR /srv
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app app
COPY data data
COPY data2 data2

ENV NETRACARE_DB=/data/netracare.db \
    PYTHONUNBUFFERED=1
RUN mkdir -p /data
VOLUME ["/data"]

EXPOSE 8000
HEALTHCHECK --interval=10s --timeout=3s --start-period=10s --retries=5 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health')"

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
