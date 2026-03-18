FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq-dev gcc && \
    rm -rf /var/lib/apt/lists/*

COPY requirements/prod.txt requirements/prod.txt
COPY requirements/base.txt requirements/base.txt
RUN pip install --no-cache-dir -r requirements/prod.txt

COPY . .

RUN python manage.py collectstatic --noinput 2>/dev/null || true

RUN groupadd -r erp && useradd -r -g erp -d /app -s /sbin/nologin erp && \
    chown -R erp:erp /app
USER erp

EXPOSE 8000

CMD ["gunicorn", "config.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "3"]
