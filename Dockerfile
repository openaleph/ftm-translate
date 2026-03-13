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

# Install CPU-only torch first (saves ~6GB vs full CUDA torch),
# then argostranslate (which depends on stanza -> torch)
RUN python -m ensurepip 2>/dev/null || true \
    && python -m pip install --no-compile \
        torch --index-url https://download.pytorch.org/whl/cpu \
    && python -m pip install --no-compile "argostranslate>=1.10.0,<2.0.0" \
    && python -m pip uninstall -y pip setuptools 2>/dev/null || true \
    && find /usr/local/lib/python*/site-packages -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true \
    && find /usr/local/lib/python*/site-packages -name "*.pyc" -delete 2>/dev/null || true

ENV FTM_TRANSLATE_ENGINE=argos
ENTRYPOINT []

# =============================================================================
# Stage: argos-offline
# Argos Translate with pre-downloaded language packages (no network needed)
#
# Build with:
#   docker build --target argos-offline \
#     --build-arg ARGOS_LANG_PAIRS="de_en es_en fr_en" \
#     -t ftm-translate:argos-offline .
#
# ARGOS_LANG_PAIRS is a space-separated list of from_to pairs (ISO 639-1).
# Default: all available packages.
# =============================================================================
FROM argos AS argos-offline

ARG ARGOS_LANG_PAIRS=""

RUN python -c "\
import argostranslate.package; \
argostranslate.package.update_package_index(); \
pairs = '${ARGOS_LANG_PAIRS}'.split(); \
available = argostranslate.package.get_available_packages(); \
to_install = [p for p in available \
    if not pairs or f'{p.from_code}_{p.to_code}' in pairs]; \
print(f'Installing {len(to_install)} language packages ...'); \
[argostranslate.package.install_from_path(p.download()) for p in to_install]; \
print('Done')"

# Pre-cache stanza resources.json inside each package's stanza/ directory so
# that stanza.Pipeline() can load it without hitting the network at runtime.
RUN python -c "\
import os, urllib.request; \
import stanza.resources.common as src; \
url = f'{src.DEFAULT_RESOURCES_URL}/resources_{src.DEFAULT_RESOURCES_VERSION}.json'; \
import argostranslate.package; \
pkgs = argostranslate.package.get_installed_packages(); \
cached = False; \
for pkg in pkgs: \
    stanza_dir = str(pkg.package_path / 'stanza'); \
    if os.path.isdir(stanza_dir): \
        res_path = os.path.join(stanza_dir, 'resources.json'); \
        if not os.path.exists(res_path): \
            if not cached: \
                urllib.request.urlretrieve(url, '/tmp/stanza_resources.json'); \
                cached = True; \
            import shutil; shutil.copy('/tmp/stanza_resources.json', res_path); \
            print(f'Cached stanza resources.json in {stanza_dir}'); \
print('Done')"

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
