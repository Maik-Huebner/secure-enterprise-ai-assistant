FROM python:3.13.9-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    UI_SERVER_NAME=0.0.0.0 \
    RUNTIME_DIR=/var/lib/novabank

WORKDIR /app

COPY requirements/lock-py313.txt /tmp/lock-py313.txt
RUN python -m pip install --index-url https://download.pytorch.org/whl/cpu \
        "torch==2.14.0+cpu" \
    && python -m pip install --no-deps -r /tmp/lock-py313.txt

COPY pyproject.toml README.md LICENSE ./
COPY src ./src
RUN python -m pip install --no-deps --no-build-isolation . \
    && addgroup --system novabank \
    && adduser --system --ingroup novabank --home /home/novabank novabank \
    && mkdir -p /var/lib/novabank \
    && chown -R novabank:novabank /var/lib/novabank

USER novabank

# One image, three entry points: novabank-api (default), novabank-ui, novabank-mcp.
# Health checks live in compose.yaml because they differ per service.
EXPOSE 8000 7860 8001

CMD ["novabank-api"]
