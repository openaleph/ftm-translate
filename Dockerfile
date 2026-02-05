# syntax=docker/dockerfile:1.4
#
# Multi-stage Dockerfile for ftm-translate with engine variant targets
#
# Build targets:
#   docker build --target argos -t ftm-translate:argos .
#   docker build --target apertium -t ftm-translate:apertium .
#
# Default target is 'argos'

ARG PYTHON_VERSION=3.13

# =============================================================================
# Stage: python-base
# Runtime base with only necessary system libraries (no build tools)
# =============================================================================
FROM python:${PYTHON_VERSION}-slim AS python-base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Runtime dependency only - libicu for pyicu
# Use wildcard for libicu version (72 on bookworm, 76 on trixie)
RUN apt-get update -qq \
    && apt-get install -qq -y --no-install-recommends \
        'libicu[0-9][0-9]' \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# =============================================================================
# Stage: builder
# Build stage with compilation tools for native extensions (e.g. CTranslate2)
# =============================================================================
FROM python-base AS builder

RUN apt-get update -qq \
    && apt-get install -qq -y --no-install-recommends \
        build-essential \
        pkg-config \
        libicu-dev \
        git \
        binutils \
    && rm -rf /var/lib/apt/lists/*

# Build pyicu wheel (requires compilation)
RUN --mount=type=cache,target=/root/.cache/pip \
    pip wheel --no-binary=:pyicu: --wheel-dir=/wheels pyicu

# =============================================================================
# Stage: deps-builder
# Install frozen dependencies from requirements.txt
# =============================================================================
FROM builder AS deps-builder

# Install pre-built pyicu wheel
RUN pip install /wheels/*.whl

# Install frozen dependencies with git available for VCS deps
COPY requirements.txt /app/requirements.txt
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install --no-compile -r requirements.txt

# Strip debug symbols from compiled extensions
RUN find /usr/local/lib/python*/site-packages -name "*.so" -exec strip --strip-unneeded {} + 2>/dev/null || true

# Remove unnecessary files from site-packages
RUN find /usr/local/lib/python*/site-packages -type d -name "tests" -exec rm -rf {} + 2>/dev/null || true \
    && find /usr/local/lib/python*/site-packages -type d -name "test" -exec rm -rf {} + 2>/dev/null || true \
    && find /usr/local/lib/python*/site-packages -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true \
    && find /usr/local/lib/python*/site-packages -name "*.pyc" -delete 2>/dev/null || true \
    && find /usr/local/lib/python*/site-packages -name "*.pyo" -delete 2>/dev/null || true \
    && find /usr/local/lib/python*/site-packages -type d -name "docs" -exec rm -rf {} + 2>/dev/null || true \
    && find /usr/local/lib/python*/site-packages -type d -name "doc" -exec rm -rf {} + 2>/dev/null || true

# =============================================================================
# Stage: deps-base (clean runtime without build tools)
# =============================================================================
FROM python-base AS deps-base

# Copy cleaned site-packages from builder
COPY --from=deps-builder /usr/local/lib/python3.13/site-packages /usr/local/lib/python3.13/site-packages
COPY --from=deps-builder /usr/local/bin /usr/local/bin

# =============================================================================
# Stage: app-base
# Application code installation (no engine extras yet)
# =============================================================================
FROM deps-base AS app-base

# Copy application code
COPY pyproject.toml setup.py VERSION README.md /app/
COPY ftm_translate /app/ftm_translate

# Install app without deps (already installed)
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install --no-deps --no-compile ".[openaleph]"

# Final cleanup - remove pip/setuptools (not needed at runtime)
RUN pip uninstall -y pip setuptools 2>/dev/null || true \
    && rm -rf /root/.cache /tmp/* \
    && find /usr/local/lib/python*/site-packages -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true

ENV PROCRASTINATE_APP="ftm_translate.tasks.app"

# =============================================================================
# Stage: argos (DEFAULT)
# Argos Translate engine
# =============================================================================
FROM app-base AS argos

RUN python -m ensurepip 2>/dev/null || true \
    && python -m pip install --no-compile "argostranslate>=1.10.0,<2.0.0" \
    && python -m pip uninstall -y pip setuptools 2>/dev/null || true \
    && find /usr/local/lib/python*/site-packages -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true \
    && find /usr/local/lib/python*/site-packages -name "*.pyc" -delete 2>/dev/null || true

ENV FTM_TRANSLATE_ENGINE=argos
ENTRYPOINT []

# =============================================================================
# Stage: apertium
# Apertium translation engine (extend image for specific language pairs)
# =============================================================================
FROM app-base AS apertium

RUN apt-get update -qq \
    && apt-get install -qq -y --no-install-recommends \
        apertium \
    && rm -rf /var/lib/apt/lists/*

ENV FTM_TRANSLATE_ENGINE=apertium
ENTRYPOINT []
