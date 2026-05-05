FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

RUN addgroup --system app && adduser --system --ingroup app app

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

USER app
EXPOSE 8082

CMD ["sh", "-c", "gunicorn -b 0.0.0.0:${SERVER_PORT:-8082} wsgi:app"]
