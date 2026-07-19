# Stage 1 — build Tailwind CSS
FROM node:20-slim AS frontend
WORKDIR /build
COPY package.json package-lock.json* tailwind.config.js ./
COPY static/css/src/ ./static/css/src/
COPY templates/ ./templates/
COPY tracker/ ./tracker/
RUN npm ci && npm run build

# Stage 2 — Python app
FROM python:3.11-slim
WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
COPY --from=frontend /build/static/css/main.css ./static/css/main.css

RUN SECRET_KEY=build-time-dummy python manage.py collectstatic --noinput

EXPOSE 8000
CMD ["sh", "-c", "python manage.py migrate --noinput && gunicorn config.wsgi:application --bind 0.0.0.0:8000 --workers 2"]
