FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
RUN DJANGO_DEBUG=true python manage.py collectstatic --noinput
EXPOSE 8000
# Migrate and seed (both idempotent) on every start; pre-deploy commands are not available on the free plan.
CMD ["sh", "-c", "python manage.py migrate --noinput && python manage.py seed_demo --users-only && gunicorn config.wsgi:application --bind 0.0.0.0:${PORT:-8000} --workers ${WEB_CONCURRENCY:-2}"]
