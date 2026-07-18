# =============================================================================
# CRIE tooling image  (Sprint 10, S10-4 · §630 docker/)
# -----------------------------------------------------------------------------
# A small image that bundles the CRIE repository plus the Python + Node + psql
# tooling used for: applying migrations, running the startup/config validation
# (R-14), seeding configuration (R-08), running the benchmark harness (Sprint 9),
# and executing the acceptance gate. It runs administrative jobs; it does NOT
# run the n8n workflows (n8n runs from the official n8nio/n8n image).
#
# Build:  docker build -f deployment/docker/Dockerfile -t crie-tools:1.0.0 .
# Run:    docker run --rm --env-file .env crie-tools:1.0.0 \
#             bash deployment/scripts/apply_migrations.sh
# =============================================================================
FROM python:3.12-slim

# --- OS deps: postgres client for psql-driven migrations; node for JS suites --
RUN apt-get update \
 && apt-get install -y --no-install-recommends \
      postgresql-client curl ca-certificates gnupg bash \
 && curl -fsSL https://deb.nodesource.com/setup_22.x | bash - \
 && apt-get install -y --no-install-recommends nodejs \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /crie

# --- python deps (pinned; see deployment/docker/requirements.txt) ---
COPY deployment/docker/requirements.txt /crie/deployment/docker/requirements.txt
RUN pip install --no-cache-dir -r deployment/docker/requirements.txt

# --- repository ---
COPY . /crie

# non-root runtime (§203 least privilege)
RUN useradd -m crie && chown -R crie:crie /crie
USER crie

# default: print the ops entrypoint help
CMD ["bash", "deployment/scripts/entrypoint.sh", "--help"]
