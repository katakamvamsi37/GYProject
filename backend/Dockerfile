FROM python:3.12-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    DJANGO_DEBUG=false \
    DJANGO_HTTP_HEALTHCHECK=true

WORKDIR /app
COPY requirements.lock.txt ./
RUN python -m pip install --no-cache-dir -r requirements.lock.txt \
    && python -m pip check \
    && groupadd --gid 10001 app \
    && useradd --uid 10001 --gid app --no-create-home app

# Explicit copies keep local databases, .env files and development keys out.
COPY manage.py gunicorn.conf.py ./
COPY config ./config
COPY core ./core
COPY docker ./docker
# Static collection needs settings, but never production secrets or a live DB.
RUN DJANGO_DEBUG=true DJANGO_SECRET_KEY=static-build-placeholder \
    python manage.py collectstatic --noinput

USER 10001:10001
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
    CMD ["python", "docker/healthcheck.py"]
CMD ["gunicorn", "--config", "gunicorn.conf.py", "config.wsgi:application"]
