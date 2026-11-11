FROM python:3.14.5-slim-bookworm AS builder
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential pkg-config default-libmysqlclient-dev \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /build
COPY requirements.txt requirements-production.txt ./
RUN python -m venv /opt/venv && /opt/venv/bin/pip install --no-cache-dir -r requirements-production.txt

FROM python:3.14.5-slim-bookworm AS runtime
RUN apt-get update && apt-get install -y --no-install-recommends \
    libmariadb3 ca-certificates libreoffice-writer fonts-liberation fonts-crosextra-carlito \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --create-home --uid 10001 santolan
ENV PATH="/opt/venv/bin:$PATH" PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 \
    PYTHON_DOTENV_DISABLED=1 DJANGO_SETTINGS_MODULE=config.settings_production \
    CERTIFICATE_OFFICE_EXECUTABLE=/usr/bin/soffice
WORKDIR /app
COPY --from=builder /opt/venv /opt/venv
COPY --chown=santolan:santolan . /app
RUN install -d -o santolan -g santolan /app/staticfiles
USER santolan
RUN test -w /app/staticfiles && python scripts/check_certificate_runtime.py
EXPOSE 10000
CMD ["sh", "/app/scripts/render-start.sh"]
