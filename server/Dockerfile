FROM python:3.12-alpine

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt \
    && addgroup -S app \
    && adduser -S app -G app

COPY app.py cache.py fetcher.py profiles.py repository.py settings.py transformer.py validator.py wsgi.py profiles.yaml ./

USER app

CMD ["gunicorn", "--bind", "0.0.0.0:25500", "--workers", "2", "--threads", "2", "wsgi:app"]
