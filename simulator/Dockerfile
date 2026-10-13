# syntax=docker/dockerfile:1
# Standard library only, so there is nothing to install and almost nothing to scan.
FROM python:3.13-alpine
RUN apk upgrade --no-cache && adduser -D -u 10002 simulator
WORKDIR /app
COPY simulate.py .
USER 10002
ENV PYTHONUNBUFFERED=1
CMD ["python", "simulate.py"]
