# syntax=docker/dockerfile:1

# ---- build stage: install dependencies into an isolated virtualenv ----
FROM python:3.13-slim AS build
ENV PIP_NO_CACHE_DIR=1 PIP_DISABLE_PIP_VERSION_CHECK=1
COPY requirements.txt /tmp/requirements.txt
# The venv gets no pip of its own; the build stage's pip installs into it.
RUN python -m venv --without-pip /opt/venv \
 && pip --python /opt/venv/bin/python install -r /tmp/requirements.txt

# ---- runtime stage: no compilers, no pip cache, non-root ----
FROM python:3.13-slim
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:$PATH"

# Pull in Debian security fixes published since the base image was built, so Trivy's
# HIGH/CRITICAL gate is not tripped by already-fixed OS packages.
#
# pip is removed too. Nothing installs packages at runtime, and pip vendors its own copies
# of urllib3, msgpack and setuptools code, which Trivy flags as HIGH whenever pip lags
# behind their fixes.
RUN apt-get update \
 && apt-get upgrade -y --no-install-recommends \
 && rm -rf /var/lib/apt/lists/* \
 && python -m pip uninstall -y pip \
 && rm -rf /usr/local/lib/python3.13/ensurepip \
 && useradd --uid 10001 --no-create-home --shell /usr/sbin/nologin argus

WORKDIR /app
COPY --from=build /opt/venv /opt/venv
COPY alembic.ini ./
COPY alembic ./alembic
COPY app ./app

USER 10001
EXPOSE 8000

HEALTHCHECK --interval=10s --timeout=3s --start-period=10s --retries=3 \
  CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=2)"]

# Migrations are deliberately NOT run here. Compose runs them in a one-shot `migrate`
# service and Kubernetes in an init container, so scaling out never races on the schema.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers", "--forwarded-allow-ips", "*"]
