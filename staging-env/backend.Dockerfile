# The API as production runs it: Python 3.12, gunicorn 23, FLASK_ENV=production.
FROM python:3.12-slim

RUN apt-get update \
 && apt-get install -y --no-install-recommends curl mariadb-client \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt requirements-dev.txt ./
RUN pip install --no-cache-dir -r requirements-dev.txt

COPY . .
ARG REVISION=unknown
RUN echo "$REVISION" > REVISION

# sitecustomize.py in this folder points Mailtrap at the local stand-in.
ENV FLASK_ENV=production \
    PYTHONPATH=/app/staging-env/python \
    PYTHONUNBUFFERED=1 \
    GUNICORN_WORKERS=3

CMD ["sh", "-c", "exec gunicorn wsgi:app --bind 0.0.0.0:6060 --workers ${GUNICORN_WORKERS} --timeout 120 --access-logfile - --error-logfile - --capture-output --log-level info"]
