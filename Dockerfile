FROM python:3.12.8-slim-bookworm
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
WORKDIR /srv
COPY requirements-runtime.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt \
 && groupadd --system app && useradd --system --gid app --home-dir /srv app \
 && mkdir -p /srv/private_uploads /srv/data \
 && chown -R app:app /srv
COPY --chown=app:app app ./app
COPY --chown=app:app migrations ./migrations
COPY --chown=app:app alembic.ini .
USER app
ENV UPLOAD_DIR=/srv/private_uploads
EXPOSE 8000
CMD ["sh","-c","uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
