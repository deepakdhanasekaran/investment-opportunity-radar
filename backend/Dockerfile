FROM python:3.12-slim AS base
ENV PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 PYTHONDONTWRITEBYTECODE=1
WORKDIR /srv
RUN useradd -r -u 10001 radar
COPY pyproject.toml ./
COPY app ./app
# Set INSTALL_SENTIMENT=1 to add FinBERT (torch, ~2GB). Without it the lexicon fallback is used.
ARG INSTALL_SENTIMENT=0
RUN pip install . && if [ "$INSTALL_SENTIMENT" = "1" ]; then pip install ".[sentiment]"; fi
COPY alembic.ini ./
COPY alembic ./alembic
COPY entrypoint.sh ./
RUN chmod +x entrypoint.sh && chown -R radar /srv
USER radar
ENTRYPOINT ["./entrypoint.sh"]
CMD ["api"]
