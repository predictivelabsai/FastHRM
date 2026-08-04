FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .

# Build provenance. A container has no git history, so the commit must be
# stamped in at build time — otherwise /about and /healthz cannot say which
# build is running. Coolify passes these through as build arguments.
ARG FASTHR_COMMIT=""
ARG FASTHR_BRANCH=""
ARG FASTHR_BUILD_DATE=""
ENV FASTHR_COMMIT=$FASTHR_COMMIT \
    FASTHR_BRANCH=$FASTHR_BRANCH \
    FASTHR_BUILD_DATE=$FASTHR_BUILD_DATE

ENV FASTHR_DB=/data/fasthr.sqlite
ENV FASTHR_UPLOAD_DIR=/data/uploads
EXPOSE 5010

# web_app.py migrates and seeds anything empty on boot, so no pre-step is needed.
CMD ["python", "web_app.py"]
