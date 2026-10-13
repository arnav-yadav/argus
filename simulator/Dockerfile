# syntax=docker/dockerfile:1
# Standard library only, so there is nothing to install and almost nothing to scan.
FROM python:3.13-alpine
# pip is removed: it is never used here, and its vendored urllib3/msgpack/setuptools
# code is the only thing Trivy finds in this image.
RUN apk upgrade --no-cache \
 && python -m pip uninstall -y pip \
 && rm -rf /usr/local/lib/python3.13/ensurepip \
 && adduser -D -u 10002 simulator
WORKDIR /app
COPY simulate.py .
USER 10002
ENV PYTHONUNBUFFERED=1
CMD ["python", "simulate.py"]
